// SPDX-License-Identifier: MIT
// Query only the statically established, byte-pinned int32_t(void) availability entry.
#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <dlfcn.h>
#include <sys/sysctl.h>
#include <cstdint>
#include <cstring>

// Preserve a real dependency without invoking the public hardware-support query.
__attribute__((used)) static auto volatile publicVTDependency=&VTIsHardwareDecodeSupported;

extern "C" void KPVideoImagesStart();
extern "C" NSDictionary *KPVideoImagesSnapshot();
extern "C" bool KPVideoPolicyBegin(CFDataRef,bool);
extern "C" void KPVideoPolicyCalibration(bool);
extern "C" NSDictionary *KPVideoPolicySnapshot();

static NSString *hash(NSData *d) {
    if(!d)return @"";unsigned char bytes[32];CC_SHA256(d.bytes,(CC_LONG)d.length,bytes);
    NSMutableString *s=[NSMutableString string];for(auto b:bytes)[s appendFormat:@"%02x",b];return s;
}
static NSData *readOwnText(const uint8_t *p,size_t count) {
    mach_vm_address_t start=(mach_vm_address_t)p;mach_vm_size_t size=0;
    vm_region_basic_info_data_64_t info{};mach_msg_type_number_t fields=VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object=MACH_PORT_NULL;
    kern_return_t status=mach_vm_region(mach_task_self(),&start,&size,VM_REGION_BASIC_INFO_64,
                                       (vm_region_info_t)&info,&fields,&object);
    if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);
    uintptr_t address=(uintptr_t)p;
    if(status||!(info.protection&VM_PROT_READ)||address<start||count>size||address-start>size-count)return nil;
    return [NSData dataWithBytes:p length:count];
}
int main(int argc,char **argv){@autoreleasepool {
    if(argc!=4)return 1;NSString *assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
    if(![@[@"inspect",@"native",@"wrong-model",@"model-entry"]containsObject:mode])return 1;
    bool inspect=[mode isEqual:@"inspect"],replace=[mode isEqual:@"wrong-model"]||[mode isEqual:@"model-entry"];
    char model[128]{};size_t n=sizeof(model);if(sysctlbyname("hw.model",model,&n,nullptr,0)||strcmp(model,"iMac11,1"))return 2;
    NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"config.json"]]options:0 error:nil];
    Dl_info policyInfo{};dladdr((void*)KPVideoPolicyBegin,&policyInfo);
    if(!config||!policyInfo.dli_fname||![hash([NSData dataWithContentsOfFile:@(policyInfo.dli_fname)])
        isEqual:config[@"policy_library_SHA256"]])return 2;
    NSString *policy=@"/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist";
    NSString *originalHash=hash([NSData dataWithContentsOfFile:policy]);
    if(![originalHash isEqual:@"e5cff89218a12c5a55b35832f13fa9552c1990d8f8100a68a7e9f0848fbfb0dc"])return 2;
    // Keep a real public VT import so its AppleVA dependency is present. Do not call it.
    if(!publicVTDependency)return 2;
    KPVideoImagesStart();NSDictionary *before=KPVideoImagesSnapshot();
    NSString *image=@"/System/Library/PrivateFrameworks/AppleVA.framework/Versions/A/AppleVA";
    bool imageMatch=false;for(NSDictionary *row in before[@"images"])
        if([row[@"install_name"]isEqual:image]&&[row[@"UUID"]isEqual:@"7533f7872ca53a968dc5fa34f9035e37"]
            &&[row[@"current_version"]isEqual:@"5.1.1"]&&[row[@"alive"]boolValue])imageMatch=true;
    if(!imageMatch)return 3;
    void *handle=dlopen(image.fileSystemRepresentation,RTLD_LAZY|RTLD_LOCAL|RTLD_NOLOAD);if(!handle)return 3;
    void *query=dlsym(handle,"VP3IsAvailable");Dl_info target{};
    if(!query||!dladdr(query,&target)||!target.dli_fname||strcmp(target.dli_fname,image.UTF8String)
        ||(uintptr_t)query-(uintptr_t)target.dli_fbase!=2484)return 3;
    struct Pin{size_t offset,bytes;const char *digest;};
    Pin pins[]={{2484,136,"47daec7d4a15839a56c0ba4ea1c77ef46341ab5b12d313eb5294574a29dfc779"},
        {267611,580,"8a6bba5a42617f54c410541bc449e3889d5d6b4ff9a93981a9e61ff35b2eaa0b"},
        {268191,1535,"25c3d2d6e7e4ded7f2e55dc30714bbe85f2b5dd12fdfcabff72e32fb4e9f8db6"}};
    NSMutableArray *checks=[NSMutableArray array];
    for(const auto &pin:pins){NSString *actual=hash(readOwnText((const uint8_t*)target.dli_fbase+pin.offset,pin.bytes));
        if(![actual isEqual:@(pin.digest)])return 4;
        [checks addObject:@{@"offset":@(pin.offset),@"bytes":@(pin.bytes),@"SHA256":actual}];}
    NSData *overlay=nil;if(replace){NSString *name=[mode stringByAppendingString:@".plist"];
        overlay=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:name]];
        if(!overlay||![hash(overlay)isEqual:config[@"overlay_SHA256"][name]])return 5;}
    if(!KPVideoPolicyBegin((CFDataRef)overlay,!inspect))return 5;
    bool calibrationModel=false;int32_t status=0;
    if(!inspect){
        KPVideoPolicyCalibration(true);CFURLRef url=CFURLCreateWithFileSystemPath(kCFAllocatorDefault,
            (CFStringRef)policy,kCFURLPOSIXPathStyle,false);CFDataRef bytes=nullptr;SInt32 error=0;
        Boolean ok=CFURLCreateDataAndPropertiesFromResource(kCFAllocatorDefault,url,&bytes,nullptr,nullptr,&error);
        KPVideoPolicyCalibration(false);CFRelease(url);if(!ok||error||!bytes)return 6;
        NSDictionary *plist=[NSPropertyListSerialization propertyListWithData:(NSData*)bytes options:0 format:nil error:nil];
        calibrationModel=plist[@"System Support"][@"iMac11,1"]!=nil;CFRelease(bytes);
        if(calibrationModel!=[mode isEqual:@"model-entry"])return 6;
        // Code and both helpers above match the inspected, zero-argument status ABI.
        status=((int32_t(*)(void))query)();
    }
    NSDictionary *trace=KPVideoPolicySnapshot();NSDictionary *after=KPVideoImagesSnapshot();
    NSString *afterHash=hash([NSData dataWithContentsOfFile:policy]);if(![afterHash isEqual:originalHash])return 7;
    NSDictionary *result=@{@"status":@"OBSERVATION_COMPLETED",@"mode":mode,@"model":@(model),
        @"image_UUID":@"7533f7872ca53a968dc5fa34f9035e37",@"resident_code_pins":checks,
        @"known_private_query_invoked":@(!inspect),@"query_abi":@"int32_t(void), pinned machine-code contract",
        @"query_status":inspect?(id)[NSNull null]:@(status),@"calibration_model_entry_present":@(calibrationModel),
        @"policy":trace,@"policy_SHA256_before":originalHash,@"policy_SHA256_after":afterHash,
        @"unknown_private_factory_or_decoder_invoked":@NO,@"hardware_video_execution_proved":@NO,
        @"system_modified":@NO,@"performance_benchmark":@NO};
    NSData *data=[NSJSONSerialization dataWithJSONObject:@{@"before":before,@"after":after}options:NSJSONWritingPrettyPrinted error:nil];
    if(![data writeToFile:[out stringByAppendingPathComponent:@"images.json"]options:0 error:nil])return 8;
    data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    fwrite(data.bytes,1,data.length,stdout);puts("");dlclose(handle);return 0;
}}
