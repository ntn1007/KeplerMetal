// SPDX-License-Identifier: MIT
// Observe the object returned to ordinary Metal; never create a device here.
#import <Foundation/Foundation.h>
#import <IOKit/IOKitLib.h>
#import <CoreFoundation/CoreFoundation.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach_vm.h>
#include <dlfcn.h>
#include <atomic>
#include <cstring>
#include <cerrno>
#include <sched.h>
extern "C" void *IOAccelDeviceCreateWithAPIProperty(io_service_t,const char*);
extern "C" int IOAccelDeviceGetConfig(void*,uint32_t*,uint32_t*,uint32_t*,uint32_t*,uint32_t*);
namespace {
std::atomic<bool> enabled{false};std::atomic<unsigned> inflight{0};std::atomic<bool> readConfig{false};std::atomic<unsigned> configCalls{0},configMatches{0},configReadFailures{0};std::atomic<int> configStatus{-1};std::atomic<uint32_t> observedValues[5]{},beforeValues[5]{},afterValues[5]{};std::atomic<unsigned> calls{0},matching{0},typeMatches{0},typeFailures{0},unqualified{0};std::atomic<uint64_t> target{0};
bool copy(uintptr_t address,void*out,size_t n){mach_vm_size_t got=0;return mach_vm_read_overwrite(mach_task_self(),address,n,(mach_vm_address_t)out,&got)==KERN_SUCCESS&&got==n;}
bool qualifiedType(CFTypeRef object){
 Dl_info i{};void*fn=(void*)&IOAccelDeviceGetConfig;if(!dladdr(fn,&i)||!i.dli_fname||strcmp(i.dli_fname,"/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator")||!i.dli_fbase||(uintptr_t)fn-(uintptr_t)i.dli_fbase!=12838)return false;
 unsigned char b[256],digest[32];if(!copy((uintptr_t)fn,b,sizeof b))return false;CC_SHA256(b,sizeof b,digest);
 const char*hex="0123456789abcdef";char actual[65]{};for(unsigned j=0;j<32;j++){actual[j*2]=hex[digest[j]>>4];actual[j*2+1]=hex[digest[j]&15];}
 if(strcmp(actual,"1f97e27b78826a4c4801f851173d67e97d00f7b1668fe5882e19895eb74b9ece"))return false;
 int32_t displacement=0;memcpy(&displacement,b+0x37,4);uint64_t expected=0;if(!copy((uintptr_t)fn+0x3b+(intptr_t)displacement,&expected,sizeof expected)||!expected)return false;
 return CFGetTypeID(object)==expected;
}
void *observe(io_service_t svc,const char *property){
 int incoming=errno;errno=incoming;void *object=IOAccelDeviceCreateWithAPIProperty(svc,property);int saved=errno;
 if(enabled.load(std::memory_order_acquire)){
  inflight.fetch_add(1);if(!enabled.load(std::memory_order_acquire)){inflight.fetch_sub(1);errno=saved;return object;}
  calls++;uint64_t rid=0;kern_return_t status=IORegistryEntryGetRegistryEntryID(svc,&rid);
  if(status==KERN_SUCCESS&&rid==target.load()&&object){matching++;if(qualifiedType((CFTypeRef)object)){
    typeMatches++;if(readConfig.load()&&configCalls.fetch_add(1)==0){
     const uintptr_t offsets[5]={0x270,0x274,0x278,0x280,0x288};uint32_t before[5]{},after[5]{},out[5]={0xdeadbeef,0xdeadbeef,0xdeadbeef,0xdeadbeef,0xdeadbeef};bool valid=true;
     for(unsigned j=0;j<5;j++){valid&=copy((uintptr_t)object+offsets[j],&before[j],sizeof(uint32_t));beforeValues[j].store(before[j]);}
     if(valid){int status=IOAccelDeviceGetConfig(object,&out[0],&out[1],&out[2],&out[3],&out[4]);configStatus.store(status);for(unsigned j=0;j<5;j++){valid&=copy((uintptr_t)object+offsets[j],&after[j],sizeof(uint32_t));observedValues[j].store(out[j]);afterValues[j].store(after[j]);valid&=before[j]==after[j]&&out[j]==before[j];}if(status==0&&valid)configMatches++;else configReadFailures++;}
     else configReadFailures++;
    }
   }else typeFailures++;}
  else if(status!=KERN_SUCCESS)unqualified++;
  inflight.fetch_sub(1);
 }
 errno=saved;return object;
}
__attribute__((used)) static const struct{const void*replacement;const void*original;} pair __attribute__((section("__DATA,__interpose")))={(const void*)&observe,(const void*)&IOAccelDeviceCreateWithAPIProperty};
}
extern "C" void KMObserveBegin(uint64_t rid,bool withConfig){target.store(rid);readConfig.store(withConfig);enabled.store(true,std::memory_order_release);}
extern "C" void KMObserveEnd(){enabled.store(false,std::memory_order_release);while(inflight.load())sched_yield();}
extern "C" NSDictionary *KMObserveResults(){return @{@"create_calls":@(calls.load()),@"matching_nonnull":@(matching.load()),@"matching_type":@(typeMatches.load()),@"type_or_profile_failures":@(typeFailures.load()),@"registry_query_failures":@(unqualified.load()),@"config_calls":@(configCalls.load()),@"config_status":@(configStatus.load()),@"config_values_match_object":@(configMatches.load()),@"config_failures":@(configReadFailures.load()),@"config_values":@[@(observedValues[0].load()),@(observedValues[1].load()),@(observedValues[2].load()),@(observedValues[3].load()),@(observedValues[4].load())],@"object_before":@[@(beforeValues[0].load()),@(beforeValues[1].load()),@(beforeValues[2].load()),@(beforeValues[3].load()),@(beforeValues[4].load())],@"object_after":@[@(afterValues[0].load()),@(afterValues[1].load()),@(afterValues[2].load()),@(afterValues[3].load()),@(afterValues[4].load())],@"return_unchanged":@YES};}
