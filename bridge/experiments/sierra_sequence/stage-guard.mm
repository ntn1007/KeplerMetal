// SPDX-License-Identifier: MIT
// Observed device words and intermediate results are simulated; final selector is refused locally.
#include <atomic>
#include <cstdint>
#include <cstring>
#include <initializer_list>
#include <IOKit/IOKitLib.h>
#include <IOKit/IOReturn.h>
extern "C" int IOAccelDeviceGetConfig(void*,void*,void*,void*,void*,void*);
extern "C" void *IOAccelDeviceCreate(uint32_t);
extern "C" void IOAccelDeviceRelease(void*);
extern "C" void *IOAccelSharedCreate(void*);
extern "C" void IOAccelSharedRelease(void*);
extern "C" void *IOAccelVideoContextCreate(void*);
extern "C" void IOAccelVideoContextRelease(void*);
extern "C" uint32_t IOAccelVideoContextGetConnect(void*);
extern "C" int IOAccelContextRequestDataBuffer(void*,uint32_t,int);
extern "C" void *IOAccelContextGetDataBufferResource(void*,uint32_t);
extern "C" int IOAccelContextSetDataBufferClassUsedBytes(void*,uint32_t);
extern "C" int IOAccelContextSubmitDataBuffers(void*,uint32_t,void*,void*);
extern "C" void *IOAccelResourceGetDataBytes(void*);
extern "C" void *IOAccelResourceGetClientShared(void*,uint32_t);
extern "C" int IOAccelVideoContextGetFenceBuffer(void*,void*,void*,void*,void*);
extern "C" int IOAccelVideoContextGetSidebandBuffer(void*,void*,void*);
extern "C" void *KPGuardFakeOriginal(unsigned);
namespace {
std::atomic<bool> armed{false};std::atomic<unsigned> refusedAfterFence{0},nextSelector{0},configCalls{0};std::atomic<unsigned> fakeCount{0},deviceCount{0},sharedCount{0},releaseCount{0},sharedReleaseCount{0},videoCreateCount{0},videoReleaseCount{0},scalarCount{0},unexpectedCount{0},connectCount{0},seenSelector{0},seenInputCount{0},seenOutputCapacity{0};std::atomic<uint64_t> seenInput0{0};
std::atomic<unsigned> sequenceCount{0};std::atomic<unsigned> sequence[4]{};
std::atomic<unsigned> extra[8]{};std::atomic<unsigned> requestClass{~0u},requestSize{0};
std::atomic<bool> resourceLive{false};std::atomic<unsigned> resourceReleased{0};
unsigned char token,sharedToken,videoToken,resourceToken;constexpr uint32_t fakeConnection=0x12345;
void *fakeGuard(unsigned){fakeCount++;return nullptr;}
int configGuard(void*p,void*a,void*b,void*c,void*d,void*e){configCalls++;if(!armed.load()||p!=&token||!a||!b||!c||!d||!e){unexpectedCount++;return kIOReturnNotPermitted;}uint32_t values[5]={768,0,0,0,1};unsigned k=0;for(void*x:{a,b,c,d,e}){memcpy(x,&values[k],4);k++;}return KERN_SUCCESS;}
void *deviceGuard(uint32_t){if(!armed.load()){unexpectedCount++;return nullptr;}deviceCount++;return &token;}
void releaseGuard(void *p){if(!armed.load()||p!=&token)unexpectedCount++;else releaseCount++;}
void *sharedGuard(void *p){if(!armed.load()||p!=&token){unexpectedCount++;return nullptr;}sharedCount++;return &sharedToken;}
void sharedReleaseGuard(void*p){if(!armed.load()||p!=&sharedToken)unexpectedCount++;else sharedReleaseCount++;}
void *videoCreateGuard(void*p){if(!armed.load()||p!=&sharedToken){unexpectedCount++;return nullptr;}videoCreateCount++;return &videoToken;}
void videoReleaseGuard(void*p){if(!armed.load()||p!=&videoToken)unexpectedCount++;else {videoReleaseCount++;if(resourceLive.exchange(false))resourceReleased++;}}
uint32_t connectGuard(void*p){if(!armed.load()||p!=&videoToken){unexpectedCount++;return 0;}connectCount++;return fakeConnection;}
kern_return_t scalarGuard(mach_port_t conn,uint32_t selector,const uint64_t*input,uint32_t n,uint64_t*output,uint32_t*count){
 scalarCount++;if(selector!=0x105){unsigned step=sequenceCount.fetch_add(1);const unsigned expected[4]={0x103,0x104,0x102,0x100};if(step<4)sequence[step].store(selector);if(!armed.load()||conn!=fakeConnection||step>=4||selector!=expected[step]||input||n!=0||!output||!count||*count!=1){unexpectedCount++;return kIOReturnNotPermitted;}output[0]=0;if(step==3){refusedAfterFence++;nextSelector.store(selector);return kIOReturnNotPermitted;}return KERN_SUCCESS;}seenSelector.store(selector);seenInputCount.store(n);
 if(!armed.load()||conn!=fakeConnection||selector!=0x105||!input||n!=1||!output||!count||*count!=2){unexpectedCount++;return kIOReturnNotPermitted;}
 seenOutputCapacity.store(*count);uint64_t value=0;memcpy(&value,input,8);seenInput0.store(value);output[0]=0;output[1]=0;return KERN_SUCCESS;
}
int requestGuard(void*ctx,uint32_t cls,int size){extra[0]++;requestClass.store(cls);requestSize.store((unsigned)size);if(!armed.load()||ctx!=&videoToken||cls!=0||size!=0x20000||resourceLive.exchange(true)){unexpectedCount++;return kIOReturnNotPermitted;}return KERN_SUCCESS;}
void *resourceGuard(void*ctx,uint32_t cls){extra[1]++;if(!armed.load()||ctx!=&videoToken||cls!=0||!resourceLive.load()){unexpectedCount++;return nullptr;}return &resourceToken;}
int usedGuard(void*,uint32_t){extra[2]++;unexpectedCount++;return kIOReturnNotPermitted;}
int submitGuard(void*,uint32_t,void*,void*){extra[3]++;unexpectedCount++;return kIOReturnNotPermitted;}
void *bytesGuard(void*){extra[4]++;unexpectedCount++;return nullptr;}
void *clientGuard(void*,uint32_t){extra[5]++;unexpectedCount++;return nullptr;}
int fenceGuard(void*ctx,void*a,void*b,void*c,void*d){extra[6]++;if(!armed.load()||ctx!=&videoToken||!resourceLive.load()||!a||!b||!c||!d){unexpectedCount++;return kIOReturnNotPermitted;}memset(a,0,8);memset(b,0,8);memset(c,0,8);memset(d,0,8);return KERN_SUCCESS;}
int sidebandGuard(void*,void*,void*){extra[7]++;unexpectedCount++;return kIOReturnNotPermitted;}
#define INTR(n,o) __attribute__((used)) static const struct{const void *a,*b;} pair_##o __attribute__((section("__DATA,__interpose")))={(const void*)&n,(const void*)&o};
INTR(fakeGuard,KPGuardFakeOriginal)
INTR(configGuard,IOAccelDeviceGetConfig)
INTR(deviceGuard,IOAccelDeviceCreate)
INTR(releaseGuard,IOAccelDeviceRelease)
INTR(sharedGuard,IOAccelSharedCreate)
INTR(sharedReleaseGuard,IOAccelSharedRelease)
INTR(videoCreateGuard,IOAccelVideoContextCreate)
INTR(videoReleaseGuard,IOAccelVideoContextRelease)
INTR(connectGuard,IOAccelVideoContextGetConnect)
INTR(scalarGuard,IOConnectCallScalarMethod)
INTR(requestGuard,IOAccelContextRequestDataBuffer)
INTR(resourceGuard,IOAccelContextGetDataBufferResource)
INTR(usedGuard,IOAccelContextSetDataBufferClassUsedBytes)
INTR(submitGuard,IOAccelContextSubmitDataBuffers)
INTR(bytesGuard,IOAccelResourceGetDataBytes)
INTR(clientGuard,IOAccelResourceGetClientShared)
INTR(fenceGuard,IOAccelVideoContextGetFenceBuffer)
INTR(sidebandGuard,IOAccelVideoContextGetSidebandBuffer)
}
extern "C" void KPStageArm(bool v){armed.store(v);}
extern "C" void *KPStageAddress(unsigned i){const void *a[]={ (const void*)&deviceGuard,(const void*)&releaseGuard,(const void*)&sharedGuard,(const void*)&sharedReleaseGuard,(const void*)&videoCreateGuard,(const void*)&videoReleaseGuard,(const void*)&scalarGuard,(const void*)&connectGuard,(const void*)&requestGuard,(const void*)&resourceGuard,(const void*)&usedGuard,(const void*)&submitGuard,(const void*)&bytesGuard,(const void*)&clientGuard,(const void*)&fenceGuard,(const void*)&sidebandGuard};return i<16?(void*)a[i]:nullptr;}
extern "C" unsigned KPStageCount(unsigned i){switch(i){case 0:return deviceCount.load();case 1:return releaseCount.load();case 2:return sharedCount.load();case 3:return sharedReleaseCount.load();case 4:return videoCreateCount.load();case 5:return videoReleaseCount.load();case 6:return scalarCount.load();case 7:return unexpectedCount.load();case 8:return fakeCount.load();case 9:return connectCount.load();default:return ~0u;}}

extern "C" unsigned KPStageSelector(){return seenSelector.load();}
extern "C" unsigned KPStageInputCount(){return seenInputCount.load();}
extern "C" unsigned KPStageOutputCapacity(){return seenOutputCapacity.load();}
extern "C" uint64_t KPStageInput0(){return seenInput0.load();}

extern "C" unsigned KPExtraCount(unsigned i){return i<8?extra[i].load():~0u;}
extern "C" unsigned KPRequestClass(){return requestClass.load();}
extern "C" unsigned KPRequestSize(){return requestSize.load();}

extern "C" unsigned KPResourceReleased(){return resourceReleased.load();}
extern "C" bool KPResourceLive(){return resourceLive.load();}

extern "C" unsigned KPProbeRefusedAfterFence(){return refusedAfterFence.load();}
extern "C" unsigned KPProbeNextSelector(){return nextSelector.load();}

extern "C" void *KPProbeConfigAddress(){return (void*)&configGuard;}
extern "C" unsigned KPProbeConfigCalls(){return configCalls.load();}

extern "C" bool KPProbeConfigCalibrate(){if(armed.exchange(true))return false;unsigned before=unexpectedCount.load();uint32_t a=1,b=2,c=3,d=4,e=5;int r=configGuard(&token,&a,&b,&c,&d,&e);armed.store(false);bool ok=r==KERN_SUCCESS&&a==768&&b==0&&c==0&&d==0&&e==1&&configCalls.load()==1&&unexpectedCount.load()==before;configCalls.store(0);return ok;}

extern "C" unsigned KPProbeSequenceCount(){return sequenceCount.load();}
extern "C" unsigned KPProbeSequence(unsigned i){return i<4?sequence[i].load():~0u;}
extern "C" bool KPProbeSequenceCalibrate(){if(armed.exchange(true))return false;unsigned before=unexpectedCount.load();uint64_t out=0x1234;uint32_t count=1;int status=scalarGuard(fakeConnection,0x104,nullptr,0,&out,&count);armed.store(false);bool ok=status==kIOReturnNotPermitted&&out==0x1234&&unexpectedCount.load()==before+1;unexpectedCount.store(before);scalarCount.store(0);sequenceCount.store(0);for(auto &x:sequence)x.store(0);return ok;}
