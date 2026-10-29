// SPDX-License-Identifier: MIT
// Bounded public IORegistry observation in our linked test process only.
#include "video_dependency.h"
#include "repeat_gate.h"
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
#include <cerrno>
#include <sched.h>
#ifndef KPDEP_RECORD
#define KPDEP_RECORD 1
#endif
#ifndef KPDEP_ENABLE
#define KPDEP_ENABLE 0
#endif
namespace {
constexpr unsigned capacity=64;
std::atomic<bool> enabled{false};
KPRepeatGate sessionGate;
std::atomic<unsigned> count{0},dropped{0},completedSessions{0};
std::atomic<unsigned> selection{0},substitutions{0};
std::atomic<bool> hardwareScope{false};
thread_local bool synthetic=false,recording=false;
uintptr_t nativeSite=0;
struct Event{
    std::atomic<bool> ready{false};bool control=false,present=false,originalPresent=false,changed=false,truncated=false,gva=false;
    uint64_t registryID=0;uint32_t service=0,options=0;int registryStatus=0;CFTypeID type=0;
    uintptr_t caller=0;char key[256]{},plane[128]{},name[128]{},className[128]{};
};
Event events[capacity];
NSString *selectionName(unsigned value){return value==2?@"present-key":(value==1?@"wrong-key":@"native");}
bool permitsSubstitution(unsigned choice,bool native,bool hardware,uint64_t registry,CFStringRef key,
    const char *plane,IOOptionBits options,bool originalPresent){
    if(!choice||!native||!hardware||originalPresent||registry!=4294968416ull||!key||
       !plane||strcmp(plane,kIOServicePlane)||options!=kIORegistryIterateRecursively)return false;
    return CFEqual(key,choice==2?CFSTR("IOGVACodec"):CFSTR("KeplerMetal-absent-dependency"));
}
bool scopeContract(){
    CFStringRef key=CFSTR("IOGVACodec");
    return permitsSubstitution(2,true,true,4294968416ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(0,true,true,4294968416ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(1,true,true,4294968416ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(2,false,true,4294968416ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(2,true,false,4294968416ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(2,true,true,4294968417ull,key,kIOServicePlane,1,false)&&
        !permitsSubstitution(2,true,true,4294968416ull,CFSTR("IOAVDHEVCDecodeCapabilities"),kIOServicePlane,1,false)&&
        !permitsSubstitution(2,true,true,4294968416ull,key,"OtherPlane",1,false)&&
        !permitsSubstitution(2,true,true,4294968416ull,key,kIOServicePlane,0,false)&&
        !permitsSubstitution(2,true,true,4294968416ull,key,kIOServicePlane,1,true);
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
       [profile[@"GPU_registry_ID"]unsignedLongLongValue]!=4294968416ull||!scopeContract())return nil;
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
        @"scope_contract_valid":@YES,@"GPU_registry_ID":@4294968416ull};
}
// Observe the additional GVA callsite, but never substitute its return.
bool gvaSite(uintptr_t caller){
 Dl_info info{};if(!dladdr((void*)caller,&info)||!info.dli_fname||!strstr(info.dli_fname,"/AppleGVA")||caller-(uintptr_t)info.dli_fbase!=149913)return false;
 uintptr_t base=(uintptr_t)info.dli_fbase;NSData*header=resident(base,sizeof(mach_header_64));if(!header)return false;auto h=(const mach_header_64*)header.bytes;if(h->magic!=MH_MAGIC_64||h->ncmds>4096||h->sizeofcmds>1048576)return false;NSData*cmds=resident(base+sizeof(*h),h->sizeofcmds);if(!cmds)return false;
 const unsigned char expected[]={0xca,0x54,0x14,0xf3,0x69,0x37,0x3c,0x05,0x9e,0xa2,0xd8,0x2b,0x35,0xaf,0xd4,0xf0};bool valid=false;size_t off=0;for(unsigned i=0;i<h->ncmds;i++){if(off+sizeof(load_command)>cmds.length)return false;auto c=(const load_command*)((const uint8_t*)cmds.bytes+off);if(c->cmdsize<sizeof(load_command)||c->cmdsize>cmds.length-off)return false;if(c->cmd==LC_UUID){if(c->cmdsize<sizeof(uuid_command)||valid)return false;valid=!memcmp(((const uuid_command*)c)->uuid,expected,sizeof(expected));}off+=c->cmdsize;}
 bool result=valid&&off==cmds.length&&[digest(resident(base+148746,2669))isEqual:@"f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19"];
 if(!result)fprintf(stderr,"KM_GVA_DEP profile_refused\n");return result;
}
__attribute__((noinline)) CFTypeRef observedSearch(io_registry_entry_t entry,const io_name_t plane,
    CFStringRef key,CFAllocatorRef allocator,IOOptionBits options){
    uintptr_t caller=(uintptr_t)__builtin_return_address(0);
    if(recording)return IORegistryEntrySearchCFProperty(entry,plane,key,allocator,options);
    const auto ticket=sessionGate.ticket();
    if(!sessionGate.enter(ticket))return IORegistryEntrySearchCFProperty(entry,plane,key,allocator,options);
    struct Leave { ~Leave(){sessionGate.leave();} } leave;
    bool gva=false;if(enabled.load(std::memory_order_seq_cst)&&KPDEP_RECORD&&!synthetic&&caller!=nativeSite){int saved=errno;recording=true;@autoreleasepool{gva=gvaSite(caller);}recording=false;errno=saved;}
    bool candidate=enabled.load(std::memory_order_seq_cst)&&(synthetic||(KPDEP_RECORD&&(caller==nativeSite||gva)));
    if(!candidate)return IORegistryEntrySearchCFProperty(entry,plane,key,allocator,options);
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
        Event &event=events[index];event.truncated=false;event.name[0]=0;event.className[0]=0;
        event.plane[0]=0;event.key[0]=0;event.control=synthetic;event.gva=gva;event.caller=caller;event.present=value!=nullptr;
        event.service=entry;event.options=options;event.type=value?CFGetTypeID(value):0;
        event.registryStatus=registryStatus;event.registryID=registryID;event.originalPresent=originalPresent;event.changed=change;
        IORegistryEntryGetName(entry,event.name);IOObjectGetClass(entry,event.className);
        if(plane){size_t n=strnlen(plane,sizeof(event.plane));event.truncated=n==sizeof(event.plane);
            memcpy(event.plane,plane,std::min(n,sizeof(event.plane)-1));}
        if(key&&!CFStringGetCString(key,event.key,sizeof(event.key),kCFStringEncodingUTF8))event.truncated=true;
        event.ready.store(true,std::memory_order_release);
    }else dropped.fetch_add(1,std::memory_order_relaxed);
    recording=false;return value;
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
    if(!sessionGate.activeOwner())return nil;
    enabled.store(false,std::memory_order_seq_cst);
    bool drained=sessionGate.close(std::chrono::milliseconds(1000));unsigned pending=0;NSMutableArray *rows=[NSMutableArray array];
    if(drained)for(unsigned i=0;i<std::min(count.load(std::memory_order_acquire),capacity);i++){
        Event &e=events[i];if(!e.ready.load(std::memory_order_acquire)){pending++;continue;}
        [rows addObject:@{@"ordinal":@(i),@"synthetic_control":@(e.control),@"service":@(e.service),
            @"registry_ID":@(e.registryID),@"registry_ID_status":@(e.registryStatus),@"name":@(e.name),
            @"class":@(e.className),@"key":@(e.key),@"plane":@(e.plane),@"options":@(e.options),
            @"result_present":@(e.present),@"original_result_present":@(e.originalPresent),
            @"return_value_changed":@(e.changed),@"CF_type":@(e.type),@"truncated":@(e.truncated),
            @"native_pinned_callsite":@(!e.control&&e.caller==nativeSite),@"GVA_pinned_callsite":@(!e.control&&e.gva)}];
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
    if(!sessionGate.reserve())return (OSStatus)-50;
    count.store(0);dropped.store(0);substitutions.store(0);
    for(auto &e:events)e.ready.store(false,std::memory_order_relaxed);
    NSDictionary *pins=prepare(@(argv[1]));bool calibrated=false;
    enabled.store(true,std::memory_order_release);
    if(!sessionGate.activate()){enabled.store(false,std::memory_order_release);sessionGate.release();return (OSStatus)-50;}
    if(pins)calibrated=calibrate();
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
    unsigned ordinal=completedSessions.fetch_add(1)+1;
    NSString *name=ordinal==1?@"dependency.json":[NSString stringWithFormat:@"dependency-%u.json",ordinal];
    bool written=[data writeToFile:[@(argv[2])stringByAppendingPathComponent:name]options:0 error:nil];
    if(modified)CFRelease(modified);
    bool drained=[record[@"recorders_drained"]boolValue];
    if(!written)fprintf(stderr,"KP_REPEAT_DEPENDENCY_RECORD_FAILED ordinal=%u\n",ordinal);
    if(drained&&!sessionGate.release())fprintf(stderr,"KP_REPEAT_DEPENDENCY_RELEASE_FAILED ordinal=%u\n",ordinal);
    return status;
}
__attribute__((used)) static const struct{const void *replacement,*original;} searchInterpose
__attribute__((section("__DATA,__interpose")))={(void*)&observedSearch,(void*)&IORegistryEntrySearchCFProperty};
__attribute__((used)) static const struct{const void *replacement,*original;} createInterpose
__attribute__((section("__DATA,__interpose")))={(void*)&observedCreate,(void*)&VTDecompressionSessionCreate};
}
extern "C" NSDictionary *KPVideoDependencyInspect(NSString *assets){
    if(!sessionGate.reserve())return nil;
    count.store(0);dropped.store(0);substitutions.store(0);
    for(auto &e:events)e.ready.store(false,std::memory_order_relaxed);
    NSDictionary *pins=prepare(assets);bool valid=false;
    enabled.store(true,std::memory_order_release);
    if(!sessionGate.activate()){enabled.store(false,std::memory_order_release);sessionGate.release();return nil;}
    if(pins)valid=calibrate();
    NSMutableDictionary *record=[NSMutableDictionary dictionaryWithDictionary:snapshot()];
    record[@"profile"]=pins?:@{};record[@"public_query_controls_valid"]=@(valid);
    record[@"public_create_called"]=@NO;record[@"hardware_video_execution_proved"]=@NO;
    if([record[@"recorders_drained"]boolValue]&&!sessionGate.release())return nil;
    return record;
}

#if defined(KPDEP_TEST) && KPDEP_TEST
// CPU-only seam: tests the real observer and scope without creating a video session.
extern "C" bool KPDependencyTestBegin(){
    if(!sessionGate.reserve())return false;
    count.store(0);dropped.store(0);substitutions.store(0);
    for(auto &e:events)e.ready.store(false,std::memory_order_relaxed);
    enabled.store(true,std::memory_order_release);
    if(sessionGate.activate())return true;
    enabled.store(false,std::memory_order_release);sessionGate.release();return false;
}
extern "C" CFTypeRef KPDependencyTestObserve(io_registry_entry_t entry,CFStringRef key){
    synthetic=true;CFTypeRef result=observedSearch(entry,kIOServicePlane,key,kCFAllocatorDefault,0);synthetic=false;return result;
}
extern "C" NSDictionary *KPDependencyTestSnapshot(){
    NSDictionary *result=snapshot();
    if(!result)return nil;
    if([result[@"recorders_drained"]boolValue]&&!sessionGate.release())return nil;
    return result;
}
#endif
