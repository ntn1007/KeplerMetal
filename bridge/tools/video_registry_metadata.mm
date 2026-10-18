// SPDX-License-Identifier: MIT
// Observe only public CFRetain at two byte-pinned CoreMedia callsites.
#include "video_registry_metadata.h"
#include <atomic>
#include <algorithm>
#include <chrono>
#include <sched.h>
#include <dlfcn.h>
namespace {
std::atomic<bool> enabled{false},configured{false};
std::atomic<unsigned> inflight{0},count{0},dropped{0};
thread_local bool control=false,copying=false;
uintptr_t sites[2]{};
#ifndef KPMETA_CAPACITY
#define KPMETA_CAPACITY 256
#endif
static_assert(KPMETA_CAPACITY>=256&&KPMETA_CAPACITY<=1024,"bounded metadata capacity");
constexpr unsigned capacity=KPMETA_CAPACITY,textCapacity=8192;
struct Event {
    std::atomic<bool> ready{false};
    bool synthetic=false,truncated=false,descriptionPresent=false;
    unsigned index=0;uintptr_t caller=0,sourceStack=0,object=0;
    CFTypeID type=0;CFIndex characters=0,converted=0,bytes=0;
    char text[textCapacity]{};
};
Event events[capacity];
__attribute__((noinline)) CFTypeRef observedRetain(CFTypeRef value) {
    // The first call always preserves the public API's ownership and return value.
    uintptr_t caller=(uintptr_t)__builtin_return_address(0);
    if(!enabled.load(std::memory_order_acquire)||copying)return CFRetain(value);
    inflight.fetch_add(1,std::memory_order_acq_rel);
    unsigned kind=caller==sites[0]?1:(caller==sites[1]?3:0);
    bool candidate=enabled.load(std::memory_order_acquire)&&(control||kind);
    if(!candidate){inflight.fetch_sub(1,std::memory_order_release);return CFRetain(value);}
    copying=true;CFTypeRef result=CFRetain(value);
    unsigned i=count.fetch_add(1,std::memory_order_relaxed);
    if(i<capacity){
        Event &e=events[i];e.synthetic=control;e.index=kind;e.caller=caller;e.object=(uintptr_t)result;
        // These two pinned private callers have the verified push-rbp/mov-rsp-rbp
        // prologue. No other caller's frame is inspected, and no item is read.
        if(!control)e.sourceStack=(uintptr_t)__builtin_frame_address(1)+8;
        if(result){
            e.type=CFGetTypeID(result);bool string=e.type==CFStringGetTypeID();
            CFStringRef description=string?(CFStringRef)result:CFCopyDescription(result);
            if(description){
                e.descriptionPresent=true;e.characters=CFStringGetLength(description);
                e.converted=CFStringGetBytes(description,CFRangeMake(0,e.characters),kCFStringEncodingUTF8,
                    0,false,(UInt8*)e.text,textCapacity-1,&e.bytes);
                e.text[e.bytes]=0;e.truncated=e.converted!=e.characters;
                if(!string)CFRelease(description);
            }
        }
        e.ready.store(true,std::memory_order_release);
    }else dropped.fetch_add(1,std::memory_order_relaxed);
    copying=false;inflight.fetch_sub(1,std::memory_order_release);return result;
}
__attribute__((used)) static const struct{const void *replacement,*original;} interpose
__attribute__((section("__DATA,__interpose")))={(void*)&observedRetain,(void*)&CFRetain};
}
extern "C" bool KPRegistryMetadataBegin(uintptr_t matching,uintptr_t description){
    if(!matching||!description||configured.exchange(true))return false;
    sites[0]=matching;sites[1]=description;enabled.store(true,std::memory_order_release);return true;
}
extern "C" void KPRegistryMetadataControl(bool value){control=value;}
extern "C" NSDictionary *KPRegistryMetadataSnapshot(){
    enabled.store(false,std::memory_order_seq_cst);
    auto end=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(inflight.load(std::memory_order_acquire)&&std::chrono::steady_clock::now()<end)sched_yield();
    bool drained=inflight.load(std::memory_order_acquire)==0;unsigned pending=0;
    NSMutableArray *rows=[NSMutableArray array];
    if(drained)for(unsigned i=0;i<std::min(count.load(std::memory_order_acquire),capacity);i++){
        Event &e=events[i];if(!e.ready.load(std::memory_order_acquire)){pending++;continue;}
        NSString *text=[[[NSString alloc]initWithBytes:e.text length:e.bytes encoding:NSUTF8StringEncoding]autorelease];
        Dl_info d{};dladdr((void*)e.caller,&d);
        [rows addObject:@{@"ordinal":@(i),@"synthetic_control":@(e.synthetic),@"private_entry_index":@(e.index),
            @"caller_PC":@(e.caller),@"caller_image":@(d.dli_fname?:""),
            @"caller_offset":@(d.dli_fbase?e.caller-(uintptr_t)d.dli_fbase:0),
            @"source_entry_stack":@(e.sourceStack),@"object_pointer":@(e.object),@"CF_type":@(e.type),
            @"description_present":@(e.descriptionPresent),@"description":text?:@"",@"truncated":@(e.truncated),
            @"characters":@(e.characters),@"characters_copied":@(e.converted)}];
    }
    return @{@"status":drained&&!pending&&!dropped.load()?@"COMPLETE":@"INCOMPLETE",
        @"recorders_drained":@(drained),@"disabled_before_snapshot":@YES,@"calls":@(count.load()),@"capacity":@(capacity),
        @"dropped":@(dropped.load()),@"pending":@(pending),@"events":rows,
        @"API":@"CFRetain/CFCopyDescription/CFString public interfaces",
        @"returned_objects_or_ownership_modified":@NO,@"opaque_registry_items_dereferenced":@NO,
        @"private_entry_invoked_directly":@NO,
        @"description_format_is_stable_API":@NO,@"system_modified":@NO};
}
