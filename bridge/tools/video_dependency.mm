// SPDX-License-Identifier: MIT
// Bounded public IORegistry observation in our linked test process only.
#include "video_dependency.h"
#import <VideoToolbox/VideoToolbox.h>
#include <IOKit/IOKitLib.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach/mach_vm.h>
#include <crt_externs.h>
#include <dlfcn.h>
#include <atomic>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <sched.h>
#ifndef KPDEP_RECORD
#define KPDEP_RECORD 1
#endif
#ifndef KPDEP_ENABLE
#define KPDEP_ENABLE 0
#endif
namespace {
constexpr unsigned capacity=64;
std::atomic<bool> enabled{false},begun{false};
std::atomic<unsigned> inflight{0},count{0},dropped{0};
std::atomic<unsigned> selection{0},substitutions{0};
std::atomic<bool> hardwareScope{false};
thread_local bool synthetic=false,recording=false;
uintptr_t nativeSite=0;
struct Event{
    std::atomic<bool> ready{false};bool control=false,present=false,originalPresent=false,changed=false,truncated=false;
    uint64_t registryID=0;uint32_t service=0,options=0;int registryStatus=0;CFTypeID type=0;
    uintptr_t caller=0;char key[256]{},plane[128]{},name[128]{},className[128]{};
};
Event events[capacity];
NSString *selectionName(unsigned value){return value==2?@"present-key":(value==1?@"wrong-key":@"native");}
bool permitsSubstitution(unsigned choice,bool native,bool hardware,uint64_t registry,CFStringRef key,
    const char *plane,IOOptionBits options,bool originalPresent){
    if(!choice||!native||!hardware||originalPresent||registry!=4294968458ull||!key||
       !plane||strcmp(plane,kIOServicePlane)||options!=kIORegistryIterateRecursively)return false;
    return CFEqual(key,choice==2?CFSTR("IOGVACodec"):CFSTR("KeplerMetal-absent-dependency"));
}
bool scopeContract(){
    CFStringRef key=CFSTR("IOGVACodec");
    return permitsSubstitution(2,true,true,4294968458ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(0,true,true,4294968458ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(1,true,true,4294968458ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(2,false,true,4294968458ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(2,true,false,4294968458ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(2,true,true,4294968459ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(2,true,true,4294968458ull,CFSTR("IOAVDHEVCDecodeCapabilities"),kIOServicePlane,1,false)&&
        !permitsSubstitution(2,true,true,4294968458ull,key,"OtherPlane",1,false)&&
        !permitsSubstitution(2,true,true,4294968458ull,key,kIOServicePlane,0,false)&&
        !permitsSubstitution(2,true,true,4294968458ull,key,kIOServicePlane,1,true);
}
NSString *digest(NSData *data){
    if(!data)return @"";unsigned char h[32];CC_SHA256(data.bytes,(CC_LONG)data.length,h);
    NSMutableString *s=[NSMutableString string];for(auto b:h)[s appendFormat:@"%02x",b];return s;
}
NSData *resident(uintptr_t address,size_t n){
    mach_vm_address_t base=address;mach_vm_size_t size=0;vm_region_basic_info_data_64_t info{};
    mach_msg_type_number_t fields=VM_REGION_BASIC_INFO_COUNT_64;mach_port_t object=MACH_PORT_NULL;
    kern_return_t status=mach_vm_region(mach_task_self(),&base,&size,VM_REGION_BASIC_INFO_64,
        (vm_region_info_t)&info,&fields,&object);
    if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);
    if(status||!(info.protection&VM_PROT_READ)||address<base||n>size||address-base>size-n)return nil;
    return [NSData dataWithBytes:(void*)address length:n];
}
NSDictionary *prepare(NSString *assets){
    NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"dependency-config.json"]]options:0 error:nil];
    NSDictionary *profile=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"dependency-profile.json"]]options:0 error:nil];
    NSDictionary *choice=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"dependency-choice.json"]]options:0 error:nil];
    Dl_info self{};
    NSString *kind=KPDEP_ENABLE?@"both":(KPDEP_RECORD?@"observer":@"passive");
    if(!config||!profile||choice.count!=1||![@[@"native",@"wrong-key",@"present-key"]containsObject:choice[@"mode"]]||
       !dladdr((void*)KPVideoDependencyInspect,&self)||!self.dli_fname||
       ![digest([NSData dataWithContentsOfFile:@(self.dli_fname)])isEqual:config[@"libraries"][kind]]||
       ![digest([NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"dependency-profile.json"]])
           isEqual:config[@"profile_SHA256"]])return nil;
    NSString *module=profile[@"module"];uintptr_t base=0;NSString *uuid=nil,*version=nil;
    if(![module isEqual:@"/System/Library/Frameworks/VideoToolbox.framework/Versions/A/VideoToolbox"]||
       ![profile[@"UUID"]isEqual:@"e7231bea63883d0a95c0a93ce970b96b"]||
       ![profile[@"version"]isEqual:@"3330.13.105"]||[profile[@"functions"]count]!=5||
       [profile[@"IORegistry_search_return_offset"]unsignedLongLongValue]!=6285217||
       [profile[@"GPU_registry_ID"]unsignedLongLongValue]!=4294968458ull||!scopeContract())return nil;
    for(uint32_t i=0;i<_dyld_image_count();i++){
        const char *name=_dyld_get_image_name(i);if(!name||strcmp(name,module.UTF8String))continue;
        auto header=(const mach_header_64*)_dyld_get_image_header(i);
        if(header->magic!=MH_MAGIC_64||header->sizeofcmds>1048576||header->ncmds>4096)return nil;
        base=(uintptr_t)header;NSData *commands=resident(base+sizeof(*header),header->sizeofcmds);
        if(!commands)return nil;size_t at=0;
        for(unsigned j=0;j<header->ncmds;j++){
            if(at+sizeof(load_command)>commands.length)return nil;
            const auto command=(const load_command*)((const uint8_t*)commands.bytes+at);
            if(command->cmdsize<sizeof(load_command)||command->cmdsize>commands.length-at)return nil;
            if(command->cmd==LC_UUID&&command->cmdsize>=sizeof(uuid_command)){
                auto u=(const uuid_command*)command;NSMutableString *s=[NSMutableString string];
                for(auto b:u->uuid)[s appendFormat:@"%02x",b];uuid=s;
            }else if(command->cmd==LC_ID_DYLIB&&command->cmdsize>=sizeof(dylib_command)){
                uint32_t v=((const dylib_command*)command)->dylib.current_version;
                version=[NSString stringWithFormat:@"%u.%u.%u",v>>16,(v>>8)&255,v&255];
            }at+=command->cmdsize;
        }
        if(at!=commands.length)return nil;break;
    }
    if(!base||![uuid isEqual:profile[@"UUID"]]||![version isEqual:profile[@"version"]])return nil;
    NSMutableArray *pins=[NSMutableArray array];
    for(NSDictionary *function in profile[@"functions"]){
        uint64_t offset=[function[@"offset"]unsignedLongLongValue],length=[function[@"bytes"]unsignedLongLongValue];
        if(!length||length>65536||offset>0x1000000||![digest(resident(base+offset,length))isEqual:function[@"SHA256"]])return nil;
        [pins addObject:@{@"offset":@(offset),@"bytes":@(length),@"SHA256":function[@"SHA256"]}];
    }
    nativeSite=base+6285217;
    selection.store([choice[@"mode"]isEqual:@"present-key"]?2:([choice[@"mode"]isEqual:@"wrong-key"]?1:0));
    return @{@"UUID":uuid,@"version":version,@"resident_code_pins":pins,@"scope_contract_cases":@10,
        @"scope_contract_valid":@YES,@"GPU_registry_ID":@4294968458ull};
}
__attribute__((noinline)) CFTypeRef observedSearch(io_registry_entry_t entry,const io_name_t plane,
    CFStringRef key,CFAllocatorRef allocator,IOOptionBits options){
    uintptr_t caller=(uintptr_t)__builtin_return_address(0);
    if(!enabled.load(std::memory_order_seq_cst)||recording)
        return IORegistryEntrySearchCFProperty(entry,plane,key,allocator,options);
    inflight.fetch_add(1,std::memory_order_seq_cst);
    bool candidate=enabled.load(std::memory_order_seq_cst)&&(synthetic||(KPDEP_RECORD&&caller==nativeSite));
    if(!candidate){inflight.fetch_sub(1,std::memory_order_seq_cst);
        return IORegistryEntrySearchCFProperty(entry,plane,key,allocator,options);}
    recording=true;
    CFTypeRef value=IORegistryEntrySearchCFProperty(entry,plane,key,allocator,options);
    bool originalPresent=value!=nullptr;uint64_t registryID=0;
    kern_return_t registryStatus=IORegistryEntryGetRegistryEntryID(entry,&registryID);
    bool change=registryStatus==KERN_SUCCESS&&permitsSubstitution(selection.load(),!synthetic&&caller==nativeSite,
        hardwareScope.load(),registryID,key,plane,options,originalPresent);
    // This is a counterfactual presence test, never a hardware capability claim.
    // The original null result owns no object. The returned public Boolean has
    // the Search API's retained ownership. All other queries stay unchanged.
    if(change){value=CFRetain(kCFBooleanTrue);substitutions.fetch_add(1);}
    unsigned index=count.fetch_add(1,std::memory_order_relaxed);
    if(index<capacity){
        Event &event=events[index];event.control=synthetic;event.caller=caller;event.present=value!=nullptr;
        event.service=entry;event.options=options;event.type=value?CFGetTypeID(value):0;
        event.registryStatus=registryStatus;event.registryID=registryID;event.originalPresent=originalPresent;event.changed=change;
        IORegistryEntryGetName(entry,event.name);IOObjectGetClass(entry,event.className);
        if(plane){size_t n=strnlen(plane,sizeof(event.plane));event.truncated=n==sizeof(event.plane);
            memcpy(event.plane,plane,std::min(n,sizeof(event.plane)-1));}
        if(key&&!CFStringGetCString(key,event.key,sizeof(event.key),kCFStringEncodingUTF8))event.truncated=true;
        event.ready.store(true,std::memory_order_release);
    }else dropped.fetch_add(1,std::memory_order_relaxed);
    recording=false;inflight.fetch_sub(1,std::memory_order_seq_cst);return value;
}
bool calibrate(){
    io_registry_entry_t root=IORegistryGetRootEntry(kIOMainPortDefault);if(!root)return false;
    CFStringRef keys[]={CFSTR("IOKitBuildVersion"),CFSTR("KeplerMetal-absent-property-control")};
    bool valid=true;
    for(unsigned i=0;i<2;i++){
        CFTypeRef expected=IORegistryEntryCreateCFProperty(root,keys[i],kCFAllocatorDefault,0);
        synthetic=true;CFTypeRef actual=observedSearch(root,kIOServicePlane,keys[i],kCFAllocatorDefault,0);synthetic=false;
        valid=valid&&((i==0)?(expected&&actual&&CFEqual(expected,actual)):(!expected&&!actual));
        if(expected)CFRelease(expected);if(actual)CFRelease(actual);
    }IOObjectRelease(root);return valid;
}
NSDictionary *snapshot(){
    enabled.store(false,std::memory_order_seq_cst);
    auto end=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(inflight.load(std::memory_order_acquire)&&std::chrono::steady_clock::now()<end)sched_yield();
    bool drained=!inflight.load(std::memory_order_acquire);unsigned pending=0;NSMutableArray *rows=[NSMutableArray array];
    if(drained)for(unsigned i=0;i<std::min(count.load(std::memory_order_acquire),capacity);i++){
        Event &e=events[i];if(!e.ready.load(std::memory_order_acquire)){pending++;continue;}
        [rows addObject:@{@"ordinal":@(i),@"synthetic_control":@(e.control),@"service":@(e.service),
            @"registry_ID":@(e.registryID),@"registry_ID_status":@(e.registryStatus),@"name":@(e.name),
            @"class":@(e.className),@"key":@(e.key),@"plane":@(e.plane),@"options":@(e.options),
            @"result_present":@(e.present),@"original_result_present":@(e.originalPresent),
            @"return_value_changed":@(e.changed),@"CF_type":@(e.type),@"truncated":@(e.truncated),
            @"native_pinned_callsite":@(!e.control&&e.caller==nativeSite)}];
    }
    return @{@"status":drained&&!pending&&!dropped.load()?@"COMPLETE":@"INCOMPLETE",@"events":rows,
        @"calls":@(count.load()),@"dropped":@(dropped.load()),@"pending":@(pending),@"recorders_drained":@(drained),
        @"disabled_before_snapshot":@YES,@"native_observation_enabled":@(KPDEP_RECORD),
        @"system_modified":@NO,@"return_value_or_ownership_modified":@(substitutions.load()!=0),
        @"return_ownership_modified":@NO,@"substitutions":@(substitutions.load()),
        @"counterfactual_selection":selectionName(selection.load()),@"opaque_registry_item_read":@NO,
        @"API":@"IORegistryEntrySearchCFProperty",@"private_function_invoked_directly":@NO};
}
OSStatus observedCreate(CFAllocatorRef allocator,CMVideoFormatDescriptionRef format,CFDictionaryRef specification,
    CFDictionaryRef attributes,const VTDecompressionOutputCallbackRecord *callback,VTDecompressionSessionRef *session){
    int argc=*_NSGetArgc();char **argv=*_NSGetArgv();
    if(argc!=4||(strcmp(argv[3],"cpu")&&strcmp(argv[3],"hardware")))
        return VTDecompressionSessionCreate(allocator,format,specification,attributes,callback,session);
    NSDictionary *pins=begun.exchange(true)?nil:prepare(@(argv[1]));bool calibrated=false;
    if(pins){enabled.store(true,std::memory_order_release);calibrated=calibrate();}
    bool required=specification&&CFDictionaryGetValue(specification,
        kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder)==kCFBooleanTrue;
    bool apply=required&&KPDEP_ENABLE;CFMutableDictionaryRef modified=nullptr;
    if(apply&&pins&&calibrated){modified=CFDictionaryCreateMutableCopy(kCFAllocatorDefault,0,specification);
        if(modified)CFDictionarySetValue(modified,kVTVideoDecoderSpecification_EnableHardwareAcceleratedVideoDecoder,kCFBooleanTrue);}
    CFDictionaryRef forwarded=modified?modified:specification;
    hardwareScope.store(required&&forwarded&&CFDictionaryGetValue(forwarded,
        kVTVideoDecoderSpecification_EnableHardwareAcceleratedVideoDecoder)==kCFBooleanTrue);
    OSStatus status=(pins&&calibrated&&(!apply||modified))?VTDecompressionSessionCreate(
        allocator,format,forwarded,attributes,callback,session):(OSStatus)-50;
    NSMutableDictionary *record=[NSMutableDictionary dictionaryWithDictionary:snapshot()];
    hardwareScope.store(false);
    record[@"profile"]=pins?:@{};record[@"public_query_controls_valid"]=@(calibrated);
    record[@"public_create_called"]=@(pins&&calibrated&&(!apply||modified));record[@"create_status"]=@(status);
    record[@"original_specification"]=specification?(id)specification:@{};
    record[@"forwarded_specification"]=forwarded?(id)forwarded:@{};record[@"both_flags_applied"]=@(modified!=nullptr);
    record[@"hardware_requirement_preserved"]=@(!required||CFDictionaryGetValue(forwarded,
        kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder)==kCFBooleanTrue);
    NSData *data=[NSJSONSerialization dataWithJSONObject:record options:NSJSONWritingPrettyPrinted error:nil];
    [data writeToFile:[@(argv[2])stringByAppendingPathComponent:@"dependency.json"]options:0 error:nil];
    if(modified)CFRelease(modified);return status;
}
__attribute__((used)) static const struct{const void *replacement,*original;} searchInterpose
__attribute__((section("__DATA,__interpose")))={(void*)&observedSearch,(void*)&IORegistryEntrySearchCFProperty};
__attribute__((used)) static const struct{const void *replacement,*original;} createInterpose
__attribute__((section("__DATA,__interpose")))={(void*)&observedCreate,(void*)&VTDecompressionSessionCreate};
}
extern "C" NSDictionary *KPVideoDependencyInspect(NSString *assets){
    NSDictionary *pins=begun.exchange(true)?nil:prepare(assets);bool valid=false;
    if(pins){enabled.store(true,std::memory_order_release);valid=calibrate();}
    NSMutableDictionary *record=[NSMutableDictionary dictionaryWithDictionary:snapshot()];
    record[@"profile"]=pins?:@{};record[@"public_query_controls_valid"]=@(valid);
    record[@"public_create_called"]=@NO;record[@"hardware_video_execution_proved"]=@NO;
    return record;
}
