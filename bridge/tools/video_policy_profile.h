// SPDX-License-Identifier: MIT
// Exact loaded-code preflight; lookup/read only, never invoke a private entry.
#pragma once
#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <dlfcn.h>
#include <sys/sysctl.h>
#include <cstring>

extern "C" void KPVideoImagesStart();
extern "C" NSDictionary *KPVideoImagesSnapshot();
extern "C" bool KPVideoPolicyBegin(CFDataRef,bool);
extern "C" void KPVideoPolicyCalibration(bool);
extern "C" NSDictionary *KPVideoPolicySnapshot();

static NSString *KPVideoHash(NSData *data) {
    if(!data)return @"";unsigned char bytes[32];
    CC_SHA256(data.bytes,(CC_LONG)data.length,bytes);NSMutableString *s=[NSMutableString string];
    for(auto b:bytes)[s appendFormat:@"%02x",b];return s;
}
static NSString *KPVideoPolicyPath() {
    return @"/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist";
}
static NSData *KPVideoOwnReadable(const uint8_t *p,size_t count) {
    mach_vm_address_t start=(mach_vm_address_t)p;mach_vm_size_t size=0;
    vm_region_basic_info_data_64_t info{};mach_msg_type_number_t fields=VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object=MACH_PORT_NULL;
    kern_return_t result=mach_vm_region(mach_task_self(),&start,&size,VM_REGION_BASIC_INFO_64,
        (vm_region_info_t)&info,&fields,&object);
    if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);
    uintptr_t address=(uintptr_t)p;
    if(result||!(info.protection&VM_PROT_READ)||address<start||count>size||address-start>size-count)return nil;
    return [NSData dataWithBytes:p length:count];
}
static NSArray *KPVideoProfilePins(NSDictionary *before,NSDictionary *config) {
    char model[128]{};size_t size=sizeof(model);
    if(sysctlbyname("hw.model",model,&size,nullptr,0)||strcmp(model,"iMac11,1"))return nil;
    Dl_info observer{};
    if(!dladdr((void*)KPVideoPolicyBegin,&observer)||!observer.dli_fname||
        ![KPVideoHash([NSData dataWithContentsOfFile:@(observer.dli_fname)])isEqual:config[@"policy_library_SHA256"]])return nil;
    if(![KPVideoHash([NSData dataWithContentsOfFile:KPVideoPolicyPath()])isEqual:
        @"e5cff89218a12c5a55b35832f13fa9552c1990d8f8100a68a7e9f0848fbfb0dc"])return nil;
    NSString *path=@"/System/Library/PrivateFrameworks/AppleVA.framework/Versions/A/AppleVA";
    bool match=false;for(NSDictionary *r in before[@"images"])
        if([r[@"install_name"]isEqual:path]&&[r[@"UUID"]isEqual:@"7533f7872ca53a968dc5fa34f9035e37"]&&
            [r[@"current_version"]isEqual:@"5.1.1"]&&[r[@"alive"]boolValue])match=true;
    if(!match)return nil;
    void *handle=dlopen(path.fileSystemRepresentation,RTLD_LAZY|RTLD_LOCAL|RTLD_NOLOAD);if(!handle)return nil;
    void *query=dlsym(handle,"VP3IsAvailable");Dl_info target{};
    bool identity=query&&dladdr(query,&target)&&target.dli_fname&&
        !strcmp(target.dli_fname,path.UTF8String)&&(uintptr_t)query-(uintptr_t)target.dli_fbase==2484;
    NSMutableArray *checks=[NSMutableArray array];
    struct Pin{size_t offset,bytes;const char *digest;};
    const Pin pins[]={{2484,136,"47daec7d4a15839a56c0ba4ea1c77ef46341ab5b12d313eb5294574a29dfc779"},
        {267611,580,"8a6bba5a42617f54c410541bc449e3889d5d6b4ff9a93981a9e61ff35b2eaa0b"},
        {268191,1535,"25c3d2d6e7e4ded7f2e55dc30714bbe85f2b5dd12fdfcabff72e32fb4e9f8db6"}};
    if(identity)for(const auto &p:pins){NSString *actual=KPVideoHash(KPVideoOwnReadable((const uint8_t*)target.dli_fbase+p.offset,p.bytes));
        if(![actual isEqual:@(p.digest)]){identity=false;break;}
        [checks addObject:@{@"offset":@(p.offset),@"bytes":@(p.bytes),@"SHA256":actual}];}
    dlclose(handle);return identity?checks:nil;
}
