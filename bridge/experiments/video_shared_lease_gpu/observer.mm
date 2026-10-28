// SPDX-License-Identifier: MIT
// Observe the object returned to ordinary Metal; never create a device here.
#import <Foundation/Foundation.h>
#include "SharedAliasGuard.h"
#include "VideoContextLease.h"
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
extern "C" void *IOAccelSharedCreate(void*);
extern "C" void *IOAccelVideoContextCreate(void*);
extern "C" void *IOAccelContextCreate(void*,uint32_t);
extern "C" void IOAccelVideoContextRelease(void*);
extern "C" uint32_t IOAccelVideoContextGetConnect(void*);
extern "C" uintptr_t IOAccelContextGetTypeID();
extern "C" uintptr_t IOAccelSharedGetTypeID();
extern "C" int IOAccelDeviceGetConfig(void*,uint32_t*,uint32_t*,uint32_t*,uint32_t*,uint32_t*);
namespace {
thread_local bool probe=false;thread_local io_connect_t probeContext=0,probeShared=0;
std::atomic<bool> requestContext{false};std::atomic<unsigned> contextAttempts{0},contextTypeMatches{0},contextSharedMatches{0},contextConnectionMatches{0},contextSlots{0},contextSlotsEmpty{0},guardsCalibrated{0},opens{0},adds{0},releases{0},denied{0},unexpected{0};std::atomic<int> openStatus{-1},addStatus{-1},releaseStatus{-1};
std::atomic<unsigned> resourceWhileContextMatches{0};
std::atomic<uintptr_t> selectedDevice{0},selectedShared{0};std::atomic<unsigned> sharedCalls{0},sharedNonNull{0},sharedArgumentMatches{0},sharedStoredMatches{0},sharedTypeMatches{0},sharedFailures{0};
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
  if(status==KERN_SUCCESS&&rid==target.load()&&object){matching++;selectedDevice.store((uintptr_t)object);if(qualifiedType((CFTypeRef)object)){
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
bool sharedType(CFTypeRef object){
 Dl_info i{},j{};void*create=(void*)&IOAccelSharedCreate,*getter=(void*)&IOAccelSharedGetTypeID;
 const char*path="/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator";
 if(!dladdr(create,&i)||!dladdr(getter,&j)||!i.dli_fname||strcmp(i.dli_fname,path)||!i.dli_fbase||j.dli_fbase!=i.dli_fbase||(uintptr_t)create-(uintptr_t)i.dli_fbase!=0x1431||(uintptr_t)getter-(uintptr_t)i.dli_fbase!=0x3e47)return false;
 auto checkHash=[](uintptr_t p,size_t n,const char*expected){unsigned char b[256],d[32];if(n>sizeof b||!copy(p,b,n))return false;CC_SHA256(b,(CC_LONG)n,d);const char*h="0123456789abcdef";char actual[65]{};for(unsigned k=0;k<32;k++){actual[2*k]=h[d[k]>>4];actual[2*k+1]=h[d[k]&15];}return !strcmp(actual,expected);};
 if(!checkHash((uintptr_t)create,251,"42cb0f1632b36c0b56a8de0fe60e1f744b8407270f309a23a6f2f30d3a33904d")||!checkHash((uintptr_t)getter,30,"d6645a880d28d4767af6cb99f1b2aa0d8b3c5b864a35aa64d114aab3d042c18b"))return false;
 unsigned char b[30];int32_t disp=0;uint64_t expected=0;if(!copy((uintptr_t)getter,b,sizeof b))return false;memcpy(&disp,b+0xd,4);
 if(!copy((uintptr_t)getter+0x11+(intptr_t)disp,&expected,sizeof expected)||!expected)return false;return CFGetTypeID(object)==expected;
}
bool contextFunctionsPinned(){
 Dl_info base{};if(!dladdr((void*)&IOAccelSharedCreate,&base)||!base.dli_fbase)return false;
 struct Pin{const void*fn;uintptr_t offset;size_t length;const char*hash;};
 const Pin pins[]={
 {(void*)&IOAccelVideoContextCreate,0x32b0,15,"8e3f084ec62d063d193bcead7fb4271012ff3334c909d1e0eba90465385e6fc6"},
 {(void*)&IOAccelContextCreate,0x1554,380,"46435a813d343f15205827de6fcc73c914701d6571c39b23431eb970b27c0e84"},
 {(void*)&IOAccelVideoContextRelease,0x58a2,17,"761d62f7a7108c48195496b607b8bb68c1cd21ca1e893ce8a6b23b9e2178d826"},
 {(void*)&IOAccelVideoContextGetConnect,0x32bf,9,"d50c5335954dfd46899efed3752740d8e38562398f089da8813d41933dc1c26d"},
 {(void*)&IOAccelContextGetTypeID,0x4377,30,"ef2dd7beb451df179ecea58f4496e6913b864ed22f2386ed0c4d0a2dc28db237"}};
 for(const auto&p:pins){Dl_info i{};unsigned char b[512],d[32];if(!dladdr(p.fn,&i)||i.dli_fbase!=base.dli_fbase||(uintptr_t)p.fn-(uintptr_t)i.dli_fbase!=p.offset||p.length>sizeof b||!copy((uintptr_t)p.fn,b,p.length))return false;CC_SHA256(b,(CC_LONG)p.length,d);const char*h="0123456789abcdef";char actual[65]{};for(unsigned k=0;k<32;k++){actual[2*k]=h[d[k]>>4];actual[2*k+1]=h[d[k]&15];}if(strcmp(actual,p.hash))return false;}
 unsigned char b[111],d[32];if(!copy((uintptr_t)base.dli_fbase+0x3906,b,sizeof b))return false;CC_SHA256(b,sizeof b,d);const char*h="0123456789abcdef";char actual[65]{};for(unsigned k=0;k<32;k++){actual[2*k]=h[d[k]>>4];actual[2*k+1]=h[d[k]&15];}return !strcmp(actual,"7eee3cf95ce9e8016084c1ecedbb87f53fe8c565939ac774c6851eaf1ea13e87");
}
kern_return_t watchOpen(io_service_t svc,task_port_t task,uint32_t type,io_connect_t*out){if(!probe)return IOServiceOpen(svc,task,type,out);opens++;uint64_t id=0;if(type!=3||task!=mach_task_self()||!out||IORegistryEntryGetRegistryEntryID(svc,&id)!=KERN_SUCCESS||id!=target.load()){unexpected++;return kIOReturnNotPermitted;}kern_return_t k=IOServiceOpen(svc,task,type,out);openStatus.store(k);if(k==KERN_SUCCESS)probeContext=*out;return k;}
kern_return_t watchAdd(io_connect_t context,io_connect_t shared){if(!probe)return IOConnectAddClient(context,shared);adds++;if(!probeContext||!probeShared||context!=probeContext||shared!=probeShared){unexpected++;return kIOReturnNotPermitted;}kern_return_t k=IOConnectAddClient(context,shared);addStatus.store(k);return k;}
kern_return_t watchRelease(io_connect_t port){if(!probe)return IOConnectRelease(port);releases++;if(!probeContext||port!=probeContext){unexpected++;return kIOReturnNotPermitted;}kern_return_t k=IOConnectRelease(port);releaseStatus.store(k);return k;}
kern_return_t watchMethod(mach_port_t c,uint32_t s,const uint64_t*i,uint32_t n,const void*p,size_t z,uint64_t*o,uint32_t*on,void*q,size_t*qn){if(probe){denied++;return kIOReturnNotPermitted;}return IOConnectCallMethod(c,s,i,n,p,z,o,on,q,qn);}
kern_return_t watchStruct(mach_port_t c,uint32_t s,const void*i,size_t n,void*o,size_t*on){if(probe){denied++;return kIOReturnNotPermitted;}return IOConnectCallStructMethod(c,s,i,n,o,on);}
kern_return_t watchScalar(mach_port_t c,uint32_t s,const uint64_t*i,uint32_t n,uint64_t*o,uint32_t*on){if(probe){denied++;return kIOReturnNotPermitted;}return IOConnectCallScalarMethod(c,s,i,n,o,on);}
#define KM_INTERPOSE(n,o) __attribute__((used)) static const struct{const void*a,*b;} pair_##o __attribute__((section("__DATA,__interpose")))={(const void*)&n,(const void*)&o};
KM_INTERPOSE(watchOpen,IOServiceOpen) KM_INTERPOSE(watchAdd,IOConnectAddClient) KM_INTERPOSE(watchRelease,IOConnectRelease)
KM_INTERPOSE(watchMethod,IOConnectCallMethod) KM_INTERPOSE(watchStruct,IOConnectCallStructMethod) KM_INTERPOSE(watchScalar,IOConnectCallScalarMethod)
bool stubMatches(uintptr_t base,uintptr_t offset,const void*expected){unsigned char b[6];int32_t disp=0;uintptr_t target=0;if(!copy(base+offset,b,sizeof b)||b[0]!=0xff||b[1]!=0x25)return false;memcpy(&disp,b+2,4);return copy(base+offset+6+(intptr_t)disp,&target,sizeof target)&&target==(uintptr_t)expected;}
bool guardReady(){
 Dl_info i{};if(!dladdr((void*)&IOAccelContextCreate,&i)||!i.dli_fbase)return false;uintptr_t base=(uintptr_t)i.dli_fbase;
 if(!stubMatches(base,0x77a6,(const void*)&watchOpen)||!stubMatches(base,0x774c,(const void*)&watchAdd)||!stubMatches(base,0x7776,(const void*)&watchRelease)||!stubMatches(base,0x775e,(const void*)&watchMethod)||!stubMatches(base,0x776a,(const void*)&watchStruct)||!stubMatches(base,0x7764,(const void*)&watchScalar))return false;
 probe=true;io_connect_t dummy=0;bool ok=watchOpen(0,mach_task_self(),99,&dummy)==kIOReturnNotPermitted&&watchAdd(0,0)==kIOReturnNotPermitted&&watchRelease(0)==kIOReturnNotPermitted&&watchMethod(0,0,nullptr,0,nullptr,0,nullptr,nullptr,nullptr,nullptr)==kIOReturnNotPermitted&&watchStruct(0,0,nullptr,0,nullptr,nullptr)==kIOReturnNotPermitted&&watchScalar(0,0,nullptr,0,nullptr,nullptr)==kIOReturnNotPermitted;probe=false;
 ok=ok&&opens.load()==1&&adds.load()==1&&releases.load()==1&&unexpected.load()==3&&denied.load()==3;opens.store(0);adds.store(0);releases.store(0);unexpected.store(0);denied.store(0);if(ok)guardsCalibrated.store(1);return ok;
}
void tryContext(void*shared,uintptr_t resource=0){
 if(!contextFunctionsPinned()||!guardReady()||!copy((uintptr_t)shared+0x18,&probeShared,sizeof probeShared)||!probeShared){unexpected++;return;}
 contextAttempts++;probe=true;void*context=IOAccelVideoContextCreate(shared);
 if(context){
  unsigned char code[30];int32_t disp=0;uint64_t expected=0;uintptr_t get=(uintptr_t)&IOAccelContextGetTypeID,stored=0;uint32_t conn=0,slots=0;
  bool valid=copy(get,code,sizeof code);if(valid){memcpy(&disp,code+0xd,4);valid=copy(get+0x11+(intptr_t)disp,&expected,sizeof expected)&&expected&&CFGetTypeID((CFTypeRef)context)==expected;}
  if(valid){contextTypeMatches++;if(copy((uintptr_t)context+0x10,&stored,sizeof stored)&&stored==(uintptr_t)shared)contextSharedMatches++;if(copy((uintptr_t)context+0x18,&conn,sizeof conn)&&conn==probeContext&&IOAccelVideoContextGetConnect(context)==conn)contextConnectionMatches++;if(copy((uintptr_t)context+0xa4,&slots,sizeof slots))contextSlots.store(slots);uintptr_t entries[16]{};if(copy((uintptr_t)context+0x20,entries,sizeof entries)){bool empty=true;for(auto x:entries)empty&=x==0;if(empty)contextSlotsEmpty.store(1);}}
  uintptr_t owner=0;if(valid&&resource&&copy(resource+0x18,&owner,sizeof owner)&&owner==(uintptr_t)shared)resourceWhileContextMatches++;
  IOAccelVideoContextRelease(context);
 }
 probe=false;probeContext=0;probeShared=0;
}
void *observeShared(void*device){
 int incoming=errno;errno=incoming;void*shared=IOAccelSharedCreate(device);int saved=errno;
 if(enabled.load(std::memory_order_acquire)){
  inflight.fetch_add(1);if(!enabled.load(std::memory_order_acquire)){inflight.fetch_sub(1);errno=saved;return shared;}
  sharedCalls++;uintptr_t selected=selectedDevice.load();if(selected&&(uintptr_t)device==selected){sharedArgumentMatches++;if(shared){sharedNonNull++;uintptr_t stored=0;if(sharedType((CFTypeRef)shared)&&copy((uintptr_t)shared+0x10,&stored,sizeof stored)){sharedTypeMatches++;if(stored==selected){sharedStoredMatches++;selectedShared.store((uintptr_t)shared);if(requestContext.load()&&contextAttempts.load()==0)tryContext(shared);}else sharedFailures++;}else sharedFailures++;}}
  inflight.fetch_sub(1);
 }
 errno=saved;return shared;
}
__attribute__((used)) static const struct{const void*replacement;const void*original;} sharedPair __attribute__((section("__DATA,__interpose")))={(const void*)&observeShared,(const void*)&IOAccelSharedCreate};
__attribute__((used)) static const struct{const void*replacement;const void*original;} pair __attribute__((section("__DATA,__interpose")))={(const void*)&observe,(const void*)&IOAccelDeviceCreateWithAPIProperty};
}
extern "C" void KMObserveBegin(uint64_t rid,bool withConfig,bool withContext){target.store(rid);readConfig.store(withConfig);requestContext.store(withContext);enabled.store(true,std::memory_order_release);}
extern "C" void KMObserveEnd(){enabled.store(false,std::memory_order_release);while(inflight.load())sched_yield();}
extern "C" NSDictionary *KMObserveResults(){return @{@"create_calls":@(calls.load()),@"matching_nonnull":@(matching.load()),@"matching_type":@(typeMatches.load()),@"type_or_profile_failures":@(typeFailures.load()),@"registry_query_failures":@(unqualified.load()),@"config_calls":@(configCalls.load()),@"config_status":@(configStatus.load()),@"config_values_match_object":@(configMatches.load()),@"config_failures":@(configReadFailures.load()),@"config_values":@[@(observedValues[0].load()),@(observedValues[1].load()),@(observedValues[2].load()),@(observedValues[3].load()),@(observedValues[4].load())],@"object_before":@[@(beforeValues[0].load()),@(beforeValues[1].load()),@(beforeValues[2].load()),@(beforeValues[3].load()),@(beforeValues[4].load())],@"object_after":@[@(afterValues[0].load()),@(afterValues[1].load()),@(afterValues[2].load()),@(afterValues[3].load()),@(afterValues[4].load())],@"resource_while_context_matches":@(resourceWhileContextMatches.load()),@"context_attempts":@(contextAttempts.load()),@"context_type_matches":@(contextTypeMatches.load()),@"context_shared_matches":@(contextSharedMatches.load()),@"context_connection_matches":@(contextConnectionMatches.load()),@"context_slots":@(contextSlots.load()),@"context_slots_empty":@(contextSlotsEmpty.load()),@"probe_guards_calibrated":@(guardsCalibrated.load()),@"probe_open_calls":@(opens.load()),@"probe_open_status":@(openStatus.load()),@"probe_add_calls":@(adds.load()),@"probe_add_status":@(addStatus.load()),@"probe_release_calls":@(releases.load()),@"probe_release_status":@(releaseStatus.load()),@"probe_denied_selectors":@(denied.load()),@"probe_unexpected":@(unexpected.load()),@"shared_calls":@(sharedCalls.load()),@"shared_matching_argument":@(sharedArgumentMatches.load()),@"shared_nonnull":@(sharedNonNull.load()),@"shared_type_matches":@(sharedTypeMatches.load()),@"shared_stored_device_matches":@(sharedStoredMatches.load()),@"shared_failures":@(sharedFailures.load()),@"return_unchanged":@YES};}

extern "C" bool KMResourceSharedMatch(uintptr_t resource){uintptr_t stored=0,shared=selectedShared.load();return resource&&shared&&copy(resource+0x18,&stored,sizeof stored)&&stored==shared;}

extern "C" bool KMResourceContextProbe(uintptr_t resource){
 uintptr_t shared=selectedShared.load();if(enabled.load()||contextAttempts.load()||!shared||!KMResourceSharedMatch(resource))return false;
 tryContext((void*)shared,resource);return contextAttempts.load()==1;
}


namespace {
struct LeaseState {
 io_connect_t metal=0, context=0, extra=0; bool releaseOnly=false, qualified=false, rejected=false, failureOutput=false;
 int beforeStatus=INT32_MIN, openedStatus=INT32_MIN, beforeCloseStatus=INT32_MIN, afterStatus=INT32_MIN;
 mach_port_urefs_t before=0,opened=0,beforeClose=0,after=0;
 bool sameName=false,metalSelf=false,extraSelf=false,objectEqual=false;
};
int leaseOpen(void*user,kepler_video::Handle service,uint32_t type,kepler_video::Handle*out){
 auto&s=*(LeaseState*)user;*out=0;
 if(type==6){s.beforeStatus=mach_port_get_refs(mach_task_self(),s.metal,MACH_PORT_RIGHT_SEND,&s.before);if(s.beforeStatus||s.before==0){s.rejected=true;return kIOReturnNotPermitted;}}
 io_connect_t c=0;int status=IOServiceOpen(service,mach_task_self(),type,&c);
 if(status!=KERN_SUCCESS){if(c)s.failureOutput=true;return status;}
 if(!c)return kIOReturnError;
 if(type==3){if(c==s.metal){s.rejected=true;return kIOReturnNotPermitted;}s.context=c;*out=c;return status;}
 if(type!=6){s.rejected=true;return kIOReturnNotPermitted;}
 s.extra=c;s.openedStatus=mach_port_get_refs(mach_task_self(),s.metal,MACH_PORT_RIGHT_SEND,&s.opened);
 s.sameName=c==s.metal;s.metalSelf=IOObjectIsEqualTo(s.metal,s.metal);s.extraSelf=IOObjectIsEqualTo(c,c);s.objectEqual=s.metalSelf&&s.extraSelf&&IOObjectIsEqualTo(s.metal,c);
 s.qualified=kepler_video::allowsReferenceRelease({true,s.sameName,s.metalSelf,s.extraSelf,s.objectEqual,s.beforeStatus,s.openedStatus,s.before,s.opened});
 if(!s.qualified||c==s.context){s.rejected=true;return kIOReturnNotPermitted;} // uncertain reference intentionally left to process exit
 *out=c;return status;
}
int leaseAssociate(void*user,kepler_video::Handle context,kepler_video::Handle shared){auto&s=*(LeaseState*)user;if(!s.qualified||context!=s.context||shared!=s.extra){s.rejected=true;return kIOReturnNotPermitted;}return IOConnectAddClient(context,shared);}
int leaseClose(void*user,kepler_video::Handle handle){
 auto&s=*(LeaseState*)user;if(handle==s.context)return IOServiceClose(handle);
 if(handle!=s.extra||!s.qualified){s.rejected=true;return kIOReturnNotPermitted;}
 s.beforeCloseStatus=mach_port_get_refs(mach_task_self(),s.metal,MACH_PORT_RIGHT_SEND,&s.beforeClose);
 if(s.beforeCloseStatus||s.beforeClose!=s.opened){s.rejected=true;return kIOReturnNotPermitted;}
 int status=s.releaseOnly?IOConnectRelease(handle):IOServiceClose(handle);
 s.afterStatus=mach_port_get_refs(mach_task_self(),s.metal,MACH_PORT_RIGHT_SEND,&s.after);return status;
}
}
extern "C" NSDictionary *KMLeaseSharedConnection(uintptr_t resource,uint64_t rid,bool releaseOnly){
 uintptr_t shared=selectedShared.load();io_connect_t metal=0;uint64_t selected=target.load();
 bool pinned=!enabled.load()&&rid==selected&&shared&&resource&&KMResourceSharedMatch(resource)&&sharedType((CFTypeRef)shared)&&copy(shared+0x18,&metal,sizeof metal)&&metal;
 if(!pinned)return @{@"status":@"PROFILE_REFUSED"};
 io_service_t svc=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(rid));uint64_t serviceID=0;
 if(!svc||IORegistryEntryGetRegistryEntryID(svc,&serviceID)!=KERN_SUCCESS||serviceID!=rid||!IOObjectConformsTo(svc,"nvAccelerator")){if(svc)IOObjectRelease(svc);return @{@"status":@"SERVICE_REFUSED"};}
 LeaseState s{};s.metal=metal;s.releaseOnly=releaseOnly;kepler_video::Backend backend{&s,leaseOpen,leaseAssociate,leaseClose};kepler_video::Lease lease(backend);
 bool started=lease.start(svc,true);bool closed=lease.close();IOObjectRelease(svc);const auto&r=lease.report();
 return @{@"status":@"OBSERVED",@"started":@(started),@"closed":@(closed),@"release_only":@(releaseOnly),@"release_qualified":@(s.qualified),@"rejected":@(s.rejected),@"failure_output_unowned":@(s.failureOutput),@"context_open_status":@(r.context_open),@"shared_open_status":@(r.shared_open),@"association_status":@(r.association),@"context_close_status":@(r.context_close),@"shared_close_status":@(r.shared_close),@"connections_distinct":@(r.distinct),@"port_names_equal":@(s.sameName),@"metal_self_equal":@(s.metalSelf),@"extra_self_equal":@(s.extraSelf),@"object_equal":@(s.objectEqual),@"refs_before_status":@(s.beforeStatus),@"refs_opened_status":@(s.openedStatus),@"refs_before_close_status":@(s.beforeCloseStatus),@"refs_after_status":@(s.afterStatus),@"refs_before":@(s.before),@"refs_opened":@(s.opened),@"refs_before_close":@(s.beforeClose),@"refs_after":@(s.after),@"explicit_video_selectors":@0,@"system_modified":@NO};
}
