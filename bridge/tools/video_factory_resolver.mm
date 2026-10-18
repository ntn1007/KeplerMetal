// SPDX-License-Identifier: MIT
// Observe the original public CFBundle resolver at one pinned native callsite.
#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach-o/loader.h>
#include <mach-o/dyld.h>
#include <mach/vm_prot.h>
#include <dlfcn.h>
#include <atomic>
#include <mutex>
#include <cstring>
#include <cerrno>
#include <sched.h>
#include <chrono>
#include <unistd.h>
#include "video_registry_observer.h"

// Exact machine ABI recovered from the complete pinned173byte body and its
// native caller. Only naturally occurring calls are forwarded. No factory is
// invoked by the observer, and no opaque registry item is dereferenced here.
extern "C" int32_t FigRegistryItemGetFactory(const void *,uint32_t,void **);

namespace {
std::atomic<bool> enabled{false},begun{false};
std::atomic<unsigned> inflight{0},count{0},dropped{0};
thread_local bool inside=false;
uintptr_t nativeSite=0;
uintptr_t acceleratorSite=0;
NSMutableArray *rows=nil,*controls=nil;
NSMutableArray *factoryRows=nil,*factoryControls=nil;
NSMutableArray *policyRows=nil;
CFDictionaryRef originalSupport=nullptr,replacementSupport=nullptr;
unsigned policyChoice=0;
std::atomic<uintptr_t> policySite{0};
std::atomic<unsigned> policyCount{0},policyChanges{0};
CFStringRef currentBoard=nullptr;
std::atomic<unsigned> factoryCount{0};
uintptr_t factoryCaller=0;
std::mutex mutex;
bool valid=false;
NSString *digest(NSData *data){
    if(!data)return @"";unsigned char h[32];CC_SHA256(data.bytes,(CC_LONG)data.length,h);
    NSMutableString *s=[NSMutableString string];for(auto b:h)[s appendFormat:@"%02x",b];return s;
}
NSDictionary *identity(const void *address){
    Dl_info info{};if(!address||!dladdr(address,&info)||!info.dli_fname||!info.dli_fbase)return nil;
    auto h=(const mach_header_64*)info.dli_fbase;
    if(h->magic!=MH_MAGIC_64||h->cputype!=CPU_TYPE_X86_64||h->ncmds>4096||h->sizeofcmds>1048576)return nil;
    size_t at=0;NSString *uuid=nil,*version=nil;uintptr_t delta=(uintptr_t)address-(uintptr_t)info.dli_fbase;
    bool text=false;
    for(unsigned i=0;i<h->ncmds;i++){
        if(at+sizeof(load_command)>h->sizeofcmds)return nil;
        auto c=(const load_command*)((const uint8_t*)(h+1)+at);
        if(c->cmdsize<sizeof(load_command)||c->cmdsize>h->sizeofcmds-at)return nil;
        if(c->cmd==LC_UUID&&c->cmdsize>=sizeof(uuid_command)){
            NSMutableString *s=[NSMutableString string];for(auto b:((const uuid_command*)c)->uuid)[s appendFormat:@"%02x",b];uuid=s;
        }else if(c->cmd==LC_ID_DYLIB&&c->cmdsize>=sizeof(dylib_command)){
            uint32_t v=((const dylib_command*)c)->dylib.current_version;
            version=[NSString stringWithFormat:@"%u.%u.%u",v>>16,(v>>8)&255,v&255];
        }else if(c->cmd==LC_SEGMENT_64&&c->cmdsize>=sizeof(segment_command_64)){
            auto s=(const segment_command_64*)c;
            if(!strncmp(s->segname,"__TEXT",16))text=(s->initprot&VM_PROT_EXECUTE)&&delta<s->vmsize;
        }at+=c->cmdsize;
    }
    if(at!=h->sizeofcmds||!uuid||!text)return nil;
    return @{@"path":@(info.dli_fname),@"UUID":uuid,@"version":version?:@"",@"has_install_version":@(version!=nil),@"offset":@(delta),
        @"symbol":info.dli_sname?@(info.dli_sname):@"",@"symbol_present":@(info.dli_sname!=nullptr),
        @"symbol_exact_address":@(info.dli_saddr==address),
        @"nearest_symbol_image_offset":@(info.dli_saddr?(uintptr_t)info.dli_saddr-(uintptr_t)info.dli_fbase:0)};
}
thread_local CFBundleRef mockBundle=nullptr;
thread_local CFStringRef mockName=nullptr;
thread_local void *mockResult=nullptr;
thread_local int mockIncoming=0,mockOutgoing=0;
thread_local bool mockValid=true;
void *mock(CFBundleRef bundle,CFStringRef name){
    mockValid&=bundle==mockBundle&&name==mockName&&errno==mockIncoming;
    errno=mockOutgoing;return mockResult;
}
void *resolve(CFBundleRef bundle,CFStringRef name,uintptr_t caller,bool test){
    int incoming=errno;
    if(!test&&(!enabled.load(std::memory_order_seq_cst)||inside||(caller!=nativeSite&&caller!=acceleratorSite))){
        errno=incoming;return CFBundleGetFunctionPointerForName(bundle,name);
    }
    inflight.fetch_add(1,std::memory_order_seq_cst);
    if(!test&&!enabled.load(std::memory_order_seq_cst)){
        inflight.fetch_sub(1);errno=incoming;return CFBundleGetFunctionPointerForName(bundle,name);
    }
    inside=true;errno=incoming;
    void *result=test?mock(bundle,name):CFBundleGetFunctionPointerForName(bundle,name);int saved=errno;
    if(!test){@autoreleasepool{
        // These are the real public CFBundle/CFString arguments, not registry
        // item pointers or guessed private object layouts.
        bool types=bundle&&name&&CFGetTypeID(bundle)==CFBundleGetTypeID()&&CFGetTypeID(name)==CFStringGetTypeID();
        CFURLRef url=types?CFBundleCopyBundleURL(bundle):nullptr;char path[2048]{},symbol[256]{};
        bool pathOK=url&&CFURLGetFileSystemRepresentation(url,true,(UInt8*)path,sizeof(path));
        bool nameOK=types&&CFStringGetCString(name,symbol,sizeof(symbol),kCFStringEncodingUTF8);
        if(url)CFRelease(url);
        unsigned index=count.fetch_add(1);
        if(index<32){
            NSDictionary *target=identity(result);
            if(caller==acceleratorSite&&result&&
                [target[@"UUID"]isEqual:@"ca5414f369373c059ea2d82b35afd4f0"]&&
                [target[@"version"]isEqual:@"10.0.20"]&&[target[@"offset"]unsignedLongLongValue]==4577){
                Dl_info image{};if(dladdr(result,&image)&&image.dli_fbase&&
                    [digest([NSData dataWithBytes:(const uint8_t*)image.dli_fbase+722087 length:1192])isEqual:
                        @"365f8095e2d41076df73fec998db936f6518ce04b21ffdf62a9765fc646670be"])
                    policySite.store((uintptr_t)image.dli_fbase+722786,std::memory_order_release);
            }
            bool accelerator=caller==acceleratorSite;
            NSDictionary *row=@{@"ordinal":@(index),@"caller_offset":@(accelerator?4294934:135582),
                @"caller_module":accelerator?@"VideoToolbox":@"CoreMedia",@"arguments_are_public_CF_types":@(types),
                @"bundle_path":pathOK?@(path):@"",@"name":nameOK?@(symbol):@"",@"truncated":@(!pathOK||!nameOK),
                @"result_present":@(result!=nullptr),@"result_identity":target?:@{},
                @"result_in_executable_image":@(target!=nil),@"arguments_forwarded_unchanged":@YES,
                @"returned_pointer_unchanged":@YES,@"function_invoked_by_observer":@NO};
            std::lock_guard<std::mutex> lock(mutex);[rows addObject:row];
        }else dropped++;
    }}
    inside=false;inflight.fetch_sub(1,std::memory_order_seq_cst);errno=saved;return result;
}
__attribute__((noinline)) void *observed(CFBundleRef bundle,CFStringRef name){
    return resolve(bundle,name,(uintptr_t)__builtin_return_address(0),false);
}
__attribute__((used)) static const struct{const void *replacement,*original;} interpose
__attribute__((section("__DATA,__interpose")))={(void*)&observed,(void*)&CFBundleGetFunctionPointerForName};
void ownMarker(){}
__attribute__((noinline)) const void *observedDictionary(CFDictionaryRef dictionary,const void *key){
    int incoming=errno;uintptr_t caller=(uintptr_t)__builtin_return_address(0);
    errno=incoming;const void *value=CFDictionaryGetValue(dictionary,key);int saved=errno;
    if(!enabled.load(std::memory_order_seq_cst)||inside||!policySite.load(std::memory_order_acquire)||
        caller!=policySite.load(std::memory_order_acquire)){errno=saved;return value;}
    inflight++;if(!enabled.load()){inflight--;errno=saved;return value;}
    inside=true;
    @autoreleasepool{
        bool type=key&&CFGetTypeID((CFTypeRef)key)==CFStringGetTypeID()&&
            value&&CFGetTypeID((CFTypeRef)value)==CFDictionaryGetTypeID();
        bool matches=type&&CFEqual(key,CFSTR("System Support"))&&originalSupport&&CFEqual(value,originalSupport);
        bool absent=matches&&currentBoard&&!CFDictionaryContainsKey((CFDictionaryRef)value,currentBoard);
        bool change=policyChoice&&replacementSupport&&matches&&absent;
        const void *before=value;if(change){value=replacementSupport;policyChanges++;}
        unsigned index=policyCount++;
        if(index<16){
            bool currentPresent=value&&currentBoard&&CFGetTypeID((CFTypeRef)value)==CFDictionaryGetTypeID()&&
                CFDictionaryContainsKey((CFDictionaryRef)value,currentBoard);
            NSDictionary *row=@{@"ordinal":@(index),@"caller_offset":@722786,@"key_is_System_Support":@(type&&CFEqual(key,CFSTR("System Support"))),
                @"original_matches_installed_support":@(matches),@"original_board_missing":@(absent),
                @"return_value_changed":@(change),@"returned_board_present":@(currentPresent),
                @"original_dictionary_modified":@NO,@"borrowed_return_contract":@YES,
                @"replacement_has_process_lifetime_owner":@(replacementSupport!=nullptr),
                @"returned_original_pointer":@(value==before)};
            std::lock_guard<std::mutex> lock(mutex);[policyRows addObject:row];
        }else dropped++;
    }
    inside=false;inflight--;errno=saved;return value;
}
__attribute__((used)) static const struct{const void *replacement,*original;} dictionaryInterpose
__attribute__((section("__DATA,__interpose")))={(void*)&observedDictionary,(void*)&CFDictionaryGetValue};
bool preparePolicy(NSString *assets){
    NSDictionary *choice=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"factory-policy-choice.json"]]options:0 error:nil];
    if(choice.count!=1||![@[@"observe",@"wrong-board",@"current-board"]containsObject:choice[@"mode"]])return false;
    policyChoice=[choice[@"mode"]isEqual:@"current-board"]?2:([choice[@"mode"]isEqual:@"wrong-board"]?1:0);
    NSData *raw=[NSData dataWithContentsOfFile:@"/System/Library/PrivateFrameworks/AppleGVA.framework/Resources/Info.plist"];
    if(![digest(raw)isEqual:@"c7cefb08fe12c1da168d8baad6b92d341ff3e331a4d2c5011de5d36bff64b3e3"])return false;
    NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"factory-policy-profile.json"]]options:0 error:nil];
    if(![config[@"board_id"]isEqual:@"Mac-F2268DAE"]||
       ![config[@"source_board"]isEqual:@"Mac-27ADBB7B4CEE8E61"])return false;
    CFPropertyListRef parsed=CFPropertyListCreateWithData(kCFAllocatorDefault,(CFDataRef)raw,kCFPropertyListImmutable,nullptr,nullptr);
    if(!parsed||CFGetTypeID(parsed)!=CFDictionaryGetTypeID()){if(parsed)CFRelease(parsed);return false;}
    auto support=(CFDictionaryRef)CFDictionaryGetValue((CFDictionaryRef)parsed,CFSTR("System Support"));
    currentBoard=(CFStringRef)CFRetain((CFStringRef)config[@"board_id"]);
    bool ok=support&&CFGetTypeID(support)==CFDictionaryGetTypeID()&&!CFDictionaryContainsKey(support,currentBoard);
    auto source=ok?CFDictionaryGetValue(support,CFSTR("Mac-27ADBB7B4CEE8E61")):nullptr;
    ok=ok&&source&&CFGetTypeID((CFTypeRef)source)==CFDictionaryGetTypeID();
    if(ok){originalSupport=(CFDictionaryRef)CFRetain(support);
        if(policyChoice){auto replacement=CFDictionaryCreateMutableCopy(kCFAllocatorDefault,0,support);
            CFDictionarySetValue(replacement,policyChoice==2?currentBoard:CFSTR("KeplerMetal-absent-board-control"),source);
            replacementSupport=replacement;}}
    CFRelease(parsed);return ok;
}
using Factory=int32_t(*)(const void *,uint32_t,void **);
thread_local bool forwardingFactory=false;
thread_local const void *factoryItem=nullptr;
thread_local uint32_t factoryFlags=0;
thread_local void **factoryOutput=nullptr;
thread_local void *factoryValue=nullptr;
thread_local int32_t factoryStatus=0;
int32_t mockFactory(const void *item,uint32_t flags,void **output){
    mockValid&=item==factoryItem&&flags==factoryFlags&&output==factoryOutput&&errno==mockIncoming;
    *output=factoryValue;errno=mockOutgoing;return factoryStatus;
}
int32_t forwardFactory(const void *item,uint32_t flags,void **output,uintptr_t caller,bool test){
    int incoming=errno;
    if(forwardingFactory){const char text[]="FACTORY_FORWARDING_CHAIN_REFUSED\n";write(2,text,sizeof(text)-1);_exit(5);}
    bool capture=!test&&enabled.load(std::memory_order_seq_cst)&&caller==factoryCaller;
    if(capture){inflight++;if(!enabled.load()) {inflight--;capture=false;}}
    forwardingFactory=true;errno=incoming;
    Factory original=test?mockFactory:(Factory)KPRegistryTail(2);
    int32_t status=original(item,flags,output);int saved=errno;
    forwardingFactory=false;
    if(capture){@autoreleasepool{
        // The original pinned implementation has just written this typed out
        // slot. The pointed-to function is identified but never called here.
        void *pointer=output?*output:nullptr;NSDictionary *target=identity(pointer);
        unsigned index=factoryCount++;
        if(index<32){
            NSDictionary *row=@{@"ordinal":@(index),@"original_caller_offset":@6289489,
                @"allow_load_uint32":@(flags),@"status_int32":@(status),@"factory_present":@(pointer!=nullptr),
                @"factory_identity":target?:@{},@"factory_pointer_unchanged":@YES,
                @"opaque_item_dereferenced_by_observer":@NO,@"typed_out_slot_observed_after_original":@YES,
                @"original_forwarded_through_qualified_entry_tail":@YES,
                @"original_caller_return_address_preserved":@NO,
                @"returned_factory_invoked_by_observer":@NO};
            std::lock_guard<std::mutex> lock(mutex);[factoryRows addObject:row];
        }else dropped++;
        inflight--;
    }}
    errno=saved;return status;
}
__attribute__((noinline)) int32_t observedFactory(const void *item,uint32_t flags,void **output){
    return forwardFactory(item,flags,output,(uintptr_t)__builtin_return_address(0),false);
}
__attribute__((used)) static const struct{const void *replacement,*original;} factoryInterpose
__attribute__((section("__DATA,__interpose")))={(void*)&observedFactory,(void*)&FigRegistryItemGetFactory};
bool calibrate(){
    bool ok=true;CFMutableDictionaryRef object=CFDictionaryCreateMutable(kCFAllocatorDefault,0,
        &kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
    if(!object)return false;
    for(unsigned i=0;i<32;i++){
        NSString *name=[NSString stringWithFormat:@"KeplerMetalResolverControl%u",i];
        mockBundle=(CFBundleRef)object;mockName=(CFStringRef)name;mockResult=i%3?(void*)ownMarker:nullptr;
        mockIncoming=500+int(i);mockOutgoing=600+int(i);mockValid=true;errno=mockIncoming;
        // Fake bundle is opaque to mock only; no native CFBundle API sees it.
        void *result=resolve(mockBundle,mockName,0,true);int actual=errno;
        bool correct=mockValid&&result==mockResult&&actual==mockOutgoing;ok&=correct;
        [controls addObject:@{@"trial":@(i),@"correct":@(correct),@"input_errno":@(mockIncoming),
            @"output_errno":@(actual),@"result_present":@(result!=nullptr),@"native_resolver_called":@NO}];
    }
    for(unsigned i=0;i<32;i++){
        void *value=nullptr;factoryItem=object;factoryFlags=(i%2)?0x80000001u:0u;factoryOutput=&value;
        factoryValue=i%3?(void*)ownMarker:nullptr;factoryStatus=i%3==0?-12692:(i%3==1?0:-12906);
        mockIncoming=700+int(i);mockOutgoing=800+int(i);mockValid=true;errno=mockIncoming;
        int32_t status=forwardFactory(factoryItem,factoryFlags,&value,0,true);int actual=errno;
        bool correct=mockValid&&value==factoryValue&&status==factoryStatus&&actual==mockOutgoing;ok&=correct;
        [factoryControls addObject:@{@"trial":@(i),@"correct":@(correct),@"status":@(status),
            @"factory_present":@(value!=nullptr),@"input_errno":@(mockIncoming),@"output_errno":@(actual),
            @"original_private_function_called":@NO}];
    }
    CFRelease(object);mockBundle=nullptr;mockName=nullptr;factoryItem=nullptr;factoryOutput=nullptr;return ok;
}
}
extern "C" bool KPVideoFactoryBegin(NSString *assets){
    if(begun.exchange(true))return false;
    NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"factory-resolver-config.json"]]options:0 error:nil];
    Dl_info self{};if(!config||config.count!=1||!dladdr((void*)KPVideoFactoryBegin,&self)||!self.dli_fname||
        ![digest([NSData dataWithContentsOfFile:@(self.dli_fname)])isEqual:config[@"library_SHA256"]])return false;
    void *entry=KPRegistryOriginal(2);NSDictionary *image=identity(entry);
    if(![image[@"path"]isEqual:@"/System/Library/Frameworks/CoreMedia.framework/Versions/A/CoreMedia"]||
       ![image[@"UUID"]isEqual:@"7c4ae5aed528396982c6a4a534949ef3"]||
       ![image[@"version"]isEqual:@"3330.13.105"]||[image[@"offset"]unsignedLongLongValue]!=135509||
       ![digest([NSData dataWithBytes:entry length:173])isEqual:
           @"57a7ef8a79a22ba025e1bd3b14c42c3462ca92db447ff9c6efeead2a98c55a16"])return false;
    // Query our already-qualified entry library for its original pointer;
    // the private function itself is never called by this observer.
    nativeSite=(uintptr_t)entry+(135582-135509);
    NSDictionary *registry=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"registry-config.json"]]options:0 error:nil];
    Dl_info tail{};
    if(!dladdr(KPRegistryTail(2),&tail)||!tail.dli_fname||
       ![@(tail.dli_fname).lastPathComponent isEqual:@"libVideoRegistry-observer.dylib"]||
       ![digest([NSData dataWithContentsOfFile:@(tail.dli_fname)])isEqual:registry[@"library_SHA256"][@"observer"]])return false;
    uintptr_t vt=0;
    for(uint32_t i=0;i<_dyld_image_count();i++){
        const char *name=_dyld_get_image_name(i);
        if(!name||strcmp(name,"/System/Library/Frameworks/VideoToolbox.framework/Versions/A/VideoToolbox"))continue;
        if(vt)return false;auto header=_dyld_get_image_header(i);NSDictionary *image=identity(header);
        if(![image[@"UUID"]isEqual:@"e7231bea63883d0a95c0a93ce970b96b"]||
           ![image[@"version"]isEqual:@"3330.13.105"])return false;vt=(uintptr_t)header;
    }
    if(!vt||![digest([NSData dataWithBytes:(void*)(vt+6288668) length:2234])isEqual:
        @"6b98a81482d8cce93ec6e651d4828edf574af91e6468b8436c484952da35d5ee"])return false;
    if(![digest([NSData dataWithBytes:(void*)(vt+4294856) length:523])isEqual:
        @"790c12ecc76f4959aa7db7047075e763e82d58819b54dc86c4ecc2d08fd002df"])return false;
    factoryCaller=vt+6289489;
    acceleratorSite=vt+4294934;
    if(!preparePolicy(assets))return false;
    rows=[[NSMutableArray alloc]init];controls=[[NSMutableArray alloc]init];policyRows=[[NSMutableArray alloc]init];
    factoryRows=[[NSMutableArray alloc]init];factoryControls=[[NSMutableArray alloc]init];valid=calibrate();
    enabled.store(valid,std::memory_order_seq_cst);return valid;
}
extern "C" NSDictionary *KPVideoFactorySnapshot(){
    enabled.store(false,std::memory_order_seq_cst);
    auto end=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(inflight.load()&&std::chrono::steady_clock::now()<end)sched_yield();
    bool drained=inflight.load()==0;NSArray *events=@[],*factories=@[],*policy=@[];
    if(drained){std::lock_guard<std::mutex> lock(mutex);events=[NSArray arrayWithArray:rows];factories=[NSArray arrayWithArray:factoryRows];policy=[NSArray arrayWithArray:policyRows];}
    return @{@"status":valid&&drained&&!dropped.load()?@"COMPLETE":@"INCOMPLETE",@"events":events,
        @"calls":@(count.load()),@"dropped":@(dropped.load()),@"recorders_drained":@(drained),
        @"controls":controls?:@[],@"synthetic_controls_valid":@(valid),@"synthetic_control_calls":@32,
        @"factory_events":factories,@"factory_calls":@(factoryCount.load()),
        @"factory_controls":factoryControls?:@[],@"factory_control_calls":@32,
        @"policy_events":policy,@"policy_calls":@(policyCount.load()),@"policy_substitutions":@(policyChanges.load()),
        @"policy_choice":policyChoice==2?@"current-board":(policyChoice==1?@"wrong-board":@"observe"),
        @"policy_system_file_modified":@NO,
        @"public_API":@"CFBundleGetFunctionPointerForName",@"caller_module_UUID":@"7c4ae5aed528396982c6a4a534949ef3",
        @"caller_return_offset":@135582,@"native_function_invoked_directly":@NO,
        @"resolved_pointer_replaced":@NO,@"arguments_modified":@NO,@"original_instructions_modified":@NO,
        @"system_modified":@NO,@"hardware_video_execution_proved":@NO,@"performance_benchmark":@NO};
}
