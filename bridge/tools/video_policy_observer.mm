// SPDX-License-Identifier: MIT
// An optional data override for one pinned availability-query callsite only.
#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
#include <atomic>
#include <cstring>
#include <pthread.h>

namespace {
std::atomic<bool> active{false}, configured{false};
thread_local bool calibration=false;
pthread_t owner{};
CFDataRef replacement=nullptr;
struct Event {bool synthetic=false,native=false,verified=false,changed=false;Boolean success=false;
    uintptr_t offset=0;char image[1024]{};};
Event events[16];unsigned count=0,dropped=0;
const char *target="/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist";
NSString *digest(CFDataRef d) {
    if(!d)return @"";unsigned char h[32];CC_SHA256(CFDataGetBytePtr(d),(CC_LONG)CFDataGetLength(d),h);
    NSMutableString *s=[NSMutableString string];for(auto x:h)[s appendFormat:@"%02x",x];return s;
}
Boolean observed(CFAllocatorRef alloc,CFURLRef url,CFDataRef *data,CFDictionaryRef *properties,
                 CFArrayRef desired,SInt32 *error) {
    void *caller=__builtin_return_address(0);
    Boolean success=CFURLCreateDataAndPropertiesFromResource(alloc,url,data,properties,desired,error);
    // Only the configuring thread can observe or replace data. The release/acquire
    // pair publishes owner/replacement; other threads never access event storage.
    if(!active.load(std::memory_order_acquire)||!pthread_equal(pthread_self(),owner))return success;
    char path[1024]{};if(!CFURLGetFileSystemRepresentation(url,true,(UInt8*)path,sizeof(path))||strcmp(path,target))return success;
    Dl_info info{};dladdr(caller,&info);uintptr_t offset=info.dli_fbase?(uintptr_t)caller-(uintptr_t)info.dli_fbase:0;
    bool native=info.dli_fname&&!strcmp(info.dli_fname,
        "/System/Library/PrivateFrameworks/AppleVA.framework/Versions/A/AppleVA")&&offset==267793;
    bool verified=success&&data&&*data&&[digest(*data)isEqual:
        @"e5cff89218a12c5a55b35832f13fa9552c1990d8f8100a68a7e9f0848fbfb0dc"];
    bool changed=false;
    if(replacement&&verified&&(native||calibration)) {
        CFDataRef old=*data;*data=(CFDataRef)CFRetain(replacement);CFRelease(old);changed=true;
    }
    if(count<16){Event &e=events[count++];e.synthetic=calibration;e.native=native;e.verified=verified;
        e.changed=changed;e.success=success;e.offset=offset;strlcpy(e.image,info.dli_fname?:"",sizeof(e.image));}
    else dropped++;
    return success;
}
__attribute__((used)) static const struct {const void *replacement,*original;} pair
__attribute__((section("__DATA,__interpose")))={(void*)&observed,(void*)&CFURLCreateDataAndPropertiesFromResource};
}
extern "C" bool KPVideoPolicyBegin(CFDataRef data,bool enable) {
    if(configured.exchange(true))return false;
    owner=pthread_self();
    if(data)replacement=(CFDataRef)CFRetain(data); // bounded, immutable, retained for this process
    active.store(enable,std::memory_order_release);return true;
}
extern "C" void KPVideoPolicyCalibration(bool value){calibration=value;}
extern "C" NSDictionary *KPVideoPolicySnapshot() {
    active.store(false,std::memory_order_release);NSMutableArray *rows=[NSMutableArray array];
    for(unsigned i=0;i<count;i++){const auto &e=events[i];[rows addObject:@{
        @"synthetic_calibration":@(e.synthetic),@"pinned_native_callsite":@(e.native),
        @"original_data_hash_verified":@(e.verified),@"return_data_changed":@(e.changed),
        @"original_success":@(e.success),@"caller_image":@(e.image),@"caller_offset":@(e.offset)}];}
    return @{@"events":rows,@"dropped":@(dropped),@"disabled_before_snapshot":@YES,
        @"system_file_modified":@NO,@"driver_instructions_modified":@NO,
        @"configuring_thread_only":@YES,
        @"scope":@"One process and one pinned AppleVA query callsite; explicit synthetic CFURL calibration"};
}
