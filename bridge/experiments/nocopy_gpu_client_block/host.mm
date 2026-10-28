// SPDX-License-Identifier: MIT
// Public Metal client; the observer only inspects naturally created objects.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <IOKit/IOKitLib.h>
#include <unistd.h>
#include <objc/runtime.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <mach/vm_region.h>
#include <dlfcn.h>
#include <CommonCrypto/CommonDigest.h>
#include <cerrno>
#include <cstring>
#include <cstdlib>
#include <atomic>
#include <chrono>
#include <time.h>
#include "race_gate.h"
#include "once_gate.h"
#include "client_state.h"
#include <memory>
@interface KMLabDeallocBase : NSObject @end
@implementation KMLabDeallocBase
-(void)dealloc {}
@end
@interface KMLabDeallocChild : KMLabDeallocBase @end
@implementation KMLabDeallocChild
-(void)dealloc {}
@end
static IMP labBaseOld=nullptr,labChildOld=nullptr;static uintptr_t labWatched=0;static unsigned labBaseCalls=0,labChildCalls=0;
using LabDealloc=void(*)(void*,SEL);
static void labBaseHook(void *p,SEL c){if((uintptr_t)p==labWatched)labBaseCalls++;((LabDealloc)labBaseOld)(p,c);}
static void labChildHook(void *p,SEL c){if((uintptr_t)p==labWatched)labChildCalls++;((LabDealloc)labChildOld)(p,c);}
static bool superCalibration(){
 SEL s=sel_registerName("dealloc");Method b=class_getInstanceMethod([KMLabDeallocBase class],s),c=class_getInstanceMethod([KMLabDeallocChild class],s);
 if(!b||!c)return false;labBaseOld=method_getImplementation(b);labChildOld=method_getImplementation(c);
 IMP prev=method_setImplementation(b,(IMP)&labBaseHook);if(prev!=labBaseOld){method_setImplementation(b,prev);return false;}
 prev=method_setImplementation(c,(IMP)&labChildHook);if(prev!=labChildOld){method_setImplementation(c,prev);method_setImplementation(b,labBaseOld);return false;}
 __weak KMLabDeallocChild *weak=nil;@autoreleasepool{__attribute__((objc_precise_lifetime)) KMLabDeallocChild *obj=[KMLabDeallocChild new];weak=obj;labWatched=(uintptr_t)(__bridge void*)obj;obj=nil;}
 bool gone=weak==nil;bool rc=method_setImplementation(c,labChildOld)==(IMP)&labChildHook;bool rb=method_setImplementation(b,labBaseOld)==(IMP)&labBaseHook;
 return gone&&rc&&rb&&labChildCalls==1&&labBaseCalls==1;
}
extern "C" bool KMResourceSharedMatch(uintptr_t);
extern "C" void KMSetReleaseWatch(uintptr_t);
extern "C" void IOAccelResourceRelease(void*);
extern "C" unsigned KMResourceEntryCount();
extern "C" unsigned KMReleaseCount();
extern "C" void KMRootWatchBegin(uintptr_t);
extern "C" void KMRootWatchEnd();
extern "C" unsigned KMRootMatches();
extern "C" void KMNestedCalibrationChild(uintptr_t);
extern "C" unsigned KMNestedCalibrationCount();
extern "C" unsigned KMNestedFinalizerCount();
extern "C" unsigned KMOuterReleaseReturns();
extern "C" NSDictionary *KMReleaseOrder();
extern "C" void KMSetRootAction(bool (*)());
extern "C" unsigned KMRepairAttempts();
extern "C" unsigned KMRepairApplied();
extern "C" unsigned KMRepairRejected();
extern "C" uintptr_t KMRootObserverAddress();
extern "C" uintptr_t KMRootOriginalAddress();
extern "C" unsigned KMResourceMetalCallerCount();
extern "C" unsigned KMStopReleaseWatch();
extern "C" bool KMResourceContextProbe(uintptr_t);
extern "C" void KMObserveBegin(uint64_t,bool,bool);
extern "C" void KMObserveEnd();
extern "C" NSDictionary *KMObserveResults();
static uint32_t value(io_registry_entry_t e,CFStringRef k){CFTypeRef x=IORegistryEntryCreateCFProperty(e,k,kCFAllocatorDefault,0);uint32_t n=0;if(x&&CFGetTypeID(x)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)x)==4){const UInt8*p=CFDataGetBytePtr((CFDataRef)x);n=p[0]|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;}if(x)CFRelease(x);return n;}
static bool ancestor(io_registry_entry_t e,uint64_t *id){if(!e||IOObjectRetain(e)!=KERN_SUCCESS)return false;io_registry_entry_t cur=e;bool found=false;for(unsigned k=0;k<32&&cur;k++){if(IOObjectConformsTo(cur,"IOPCIDevice")){uint64_t rid=0;found=value(cur,CFSTR("vendor-id"))==0x10de&&value(cur,CFSTR("device-id"))==0x1198&&IORegistryEntryGetRegistryEntryID(cur,&rid)==KERN_SUCCESS&&rid;if(found)*id=rid;break;}io_registry_entry_t p=0;kern_return_t st=IORegistryEntryGetParentEntry(cur,kIOServicePlane,&p);IOObjectRelease(cur);cur=0;if(st!=KERN_SUCCESS)break;cur=p;}if(cur)IOObjectRelease(cur);return found;}
static bool readBytes(uintptr_t address,void *out,size_t size){mach_vm_size_t n=0;return mach_vm_read_overwrite(mach_task_self(),address,size,(mach_vm_address_t)out,&n)==KERN_SUCCESS&&n==size;}
static std::atomic<uintptr_t> watchedObject{0},watchedResourceObject{0},expectedBlock{0};
static std::atomic<unsigned> blockAtDeallocRead{0},blockAtDeallocNonzero{0},blockAtDeallocMatches{0};
static uintptr_t blockIvarOffset=0;static bool blockIvarPinned=false,blockBeforeRead=false,blockBeforeNonzero=false,blockBeforeMatches=false;
static void (^heldExpectedBlock)(void*,NSUInteger)=nil;
static std::atomic<unsigned> noCopyDeallocCalls{0},noCopyBadArgs{0},callbackAttempts{0},callbackDuplicates{0},syntheticLateCalls{0},unapprovedCallbacks{0},rootReturnedEvents{0};static std::atomic<int> vmBeforeRelease{-1},vmAfterRelease{-1},vmReleaseStatus{-1};static std::atomic<bool> releaseAuthorized{false};static std::atomic<bool> noCopyFreed{false},witnessTaken{false};
static uintptr_t witnessPointer=0;static size_t witnessLength=0;static bool witnessPolicy=true,gpuRequested=false;
static kepler_witness::RaceGate raceGate;
static std::atomic<bool> gpuCompleted{false};static std::atomic<unsigned> gpuGateRefusals{0},gpuDeferredApplied{0},gpuHandlerCount{0},gpuHandlerStatus{0},gpuHandlerAtRefusal{0};static bool gpuPrecommitWeakAlive=false;static unsigned gpuPrecommitCallbacks=0;static unsigned gpuDispatches=0,gpuStatus=0,gpuSecondStatus=0,gpuSecondAtFirstWait=0,gpuAfterFirstCallbacks=0,gpuMismatches=0;static NSMutableArray *gpuWords=nil;

static std::atomic<unsigned> bufferDeallocs{0},resourceDeallocs{0},resourceFieldMatches{0},nvDeallocs{0},branchKnown{0},directCandidate{0};
static int covers(uintptr_t,size_t);
static KMClientState clientState{};
static bool deliverWitness(){
 bool expected=false;if(!witnessPolicy||!witnessPointer||witnessLength!=4096||blockAtDeallocMatches.load()!=1||directCandidate.load()!=1||noCopyDeallocCalls.load()!=0||!heldExpectedBlock||!witnessTaken.compare_exchange_strong(expected,true))return false;
 releaseAuthorized.store(true);heldExpectedBlock((void*)witnessPointer,witnessLength);releaseAuthorized.store(false);return noCopyFreed.load();
}
static bool invokeWitness(){
 if(!witnessPolicy||!witnessPointer||witnessLength!=4096||blockAtDeallocMatches.load()!=1||directCandidate.load()!=1)return false;
 auto decision=raceGate.root();
 if(decision==kepler_witness::Decision::waiting){gpuHandlerAtRefusal.store(gpuHandlerCount.load());gpuGateRefusals++;return false;}
 return decision==kepler_witness::Decision::deliver&&deliverWitness();
}
static IMP oldBuffer=nullptr,oldResource=nullptr,oldNV=nullptr;static Method bufferMethod=nullptr,resourceMethod=nullptr,nvMethod=nullptr;
using DeallocProc=void(*)(void*,SEL);
static void hookNV(void *self,SEL cmd){
 bool watching=(uintptr_t)self==watchedObject.load();
 if(watching){
  nvDeallocs++;uintptr_t device=0;uint64_t flags=0;uint8_t policy=0;uintptr_t block=0;
  if(blockIvarPinned&&readBytes((uintptr_t)self+blockIvarOffset,&block,sizeof block)){blockAtDeallocRead++;if(block)blockAtDeallocNonzero++;if(block&&block==expectedBlock.load())blockAtDeallocMatches++;}
  bool known=readBytes((uintptr_t)self+0x18,&device,sizeof device)&&readBytes((uintptr_t)self+0xa8,&flags,sizeof flags);
  if(known&&device){known=device<=UINTPTR_MAX-0x371&&readBytes(device+0x371,&policy,sizeof policy);}
  if(known){branchKnown++;if(!(policy&0x20)&&(flags&0x1000000000000000ull))directCandidate++;}
 }
 if(watching)KMRootWatchBegin((uintptr_t)self);((DeallocProc)oldNV)(self,cmd);
 if(watching){KMRootWatchEnd();if(witnessPolicy&&gpuRequested){rootReturnedEvents++;auto d=raceGate.root_returned();if(d==kepler_witness::Decision::deliver&&deliverWitness())gpuDeferredApplied++;}}
}
static void hookBuffer(void *self,SEL cmd){if((uintptr_t)self==watchedObject.load())bufferDeallocs++;((DeallocProc)oldBuffer)(self,cmd);}
static void hookResource(void *self,SEL cmd){if((uintptr_t)self==watchedObject.load()){resourceDeallocs++;uintptr_t field=0;if(readBytes((uintptr_t)self+0x88,&field,sizeof field)&&field==watchedResourceObject.load())resourceFieldMatches++;}((DeallocProc)oldResource)(self,cmd);}
static bool pinMethod(IMP imp,uintptr_t offset,size_t len,const char*expected){
 Dl_info i{};unsigned char b[512],h[32];char hex[65]{};const char*d="0123456789abcdef";
 if(!imp||len>sizeof b||!dladdr((void*)imp,&i)||!i.dli_fname||strcmp(i.dli_fname,"/System/Library/Frameworks/Metal.framework/Versions/A/MetalOld.dylib")||!i.dli_fbase||(uintptr_t)imp-(uintptr_t)i.dli_fbase!=offset||!readBytes((uintptr_t)imp,b,len))return false;
 CC_SHA256(b,(CC_LONG)len,h);for(unsigned j=0;j<32;j++){hex[j*2]=d[h[j]>>4];hex[j*2+1]=d[h[j]&15];}return !strcmp(hex,expected);
}
static bool installHooks(){
 Class b=objc_getClass("MTLIOAccelBuffer"),r=objc_getClass("MTLIOAccelResource"),n=objc_getClass("NVMTLBuffer");SEL sel=sel_registerName("dealloc");
 if(!b||!r||!n||class_getSuperclass(b)!=r||class_getSuperclass(n)!=b)return false;
 Ivar blockIvar=class_getInstanceVariable(b,"_deallocator");const char *blockType=blockIvar?ivar_getTypeEncoding(blockIvar):nullptr;ptrdiff_t blockOffset=blockIvar?ivar_getOffset(blockIvar):-1;
 blockIvarPinned=blockType&&!strcmp(blockType,"@?")&&blockOffset>=0&&(size_t)blockOffset+sizeof(uintptr_t)<=class_getInstanceSize(b);if(!blockIvarPinned)return false;blockIvarOffset=(uintptr_t)blockOffset;
 bufferMethod=class_getInstanceMethod(b,sel);resourceMethod=class_getInstanceMethod(r,sel);nvMethod=class_getInstanceMethod(n,sel);
 if(!bufferMethod||!resourceMethod||!nvMethod||strcmp(method_getTypeEncoding(bufferMethod),"v16@0:8")||strcmp(method_getTypeEncoding(resourceMethod),"v16@0:8")||strcmp(method_getTypeEncoding(nvMethod),"v16@0:8"))return false;
 oldBuffer=method_getImplementation(bufferMethod);oldResource=method_getImplementation(resourceMethod);oldNV=method_getImplementation(nvMethod);
 if(!pinMethod(oldBuffer,0x27626,346,"6cab41cb080100a7b7d1099c99fa807c5210636c0b2900932e9415bb12b09964")||!pinMethod(oldResource,0x27780,368,"31fa01138e29ac6b1a65804473d05f787fb3f108ba9fc59ca14b3ac64a59dd93"))return false;
 Dl_info nvInfo{};unsigned char nvBytes[399],nvHash[32];char nvHex[65]{};const char*d="0123456789abcdef";
 if(!dladdr((void*)oldNV,&nvInfo)||!nvInfo.dli_fname||strcmp(nvInfo.dli_fname,"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver")||!nvInfo.dli_fbase||(uintptr_t)oldNV-(uintptr_t)nvInfo.dli_fbase!=0xcf1c6||!readBytes((uintptr_t)oldNV,nvBytes,sizeof nvBytes))return false;
 CC_SHA256(nvBytes,sizeof nvBytes,nvHash);for(unsigned i=0;i<32;i++){nvHex[2*i]=d[nvHash[i]>>4];nvHex[2*i+1]=d[nvHash[i]&15];}if(strcmp(nvHex,"4f7920d3f230d28718d9b692cc08869da9b8c9f4d8b4289ec4871d81cf08dfc3"))return false;
 IMP previous=method_setImplementation(resourceMethod,(IMP)&hookResource);if(previous!=oldResource){method_setImplementation(resourceMethod,previous);return false;}
 previous=method_setImplementation(bufferMethod,(IMP)&hookBuffer);if(previous!=oldBuffer){method_setImplementation(bufferMethod,previous);method_setImplementation(resourceMethod,oldResource);return false;}previous=method_setImplementation(nvMethod,(IMP)&hookNV);if(previous!=oldNV){method_setImplementation(nvMethod,previous);method_setImplementation(bufferMethod,oldBuffer);method_setImplementation(resourceMethod,oldResource);return false;}return true;
}
static bool restoreHooks(){
 if(method_getImplementation(nvMethod)!=(IMP)&hookNV||method_getImplementation(bufferMethod)!=(IMP)&hookBuffer||method_getImplementation(resourceMethod)!=(IMP)&hookResource)return false;
 bool n=method_setImplementation(nvMethod,oldNV)==(IMP)&hookNV;bool b=method_setImplementation(bufferMethod,oldBuffer)==(IMP)&hookBuffer;bool r=method_setImplementation(resourceMethod,oldResource)==(IMP)&hookResource;return n&&b&&r;
}
struct Snapshot {uintptr_t fields[2]{};bool valid=false;};
static Snapshot snapshots[2];static unsigned snapshotCount=0;
static void syntheticArrayRelease(CFAllocatorRef, const void *value){CFRelease((CFTypeRef)value);}
static bool nestedCalibration(){
 CFMutableArrayRef array=nullptr;CFDataRef data=CFDataCreate(kCFAllocatorDefault,(const UInt8*)"A",1);if(!data)return false;
 CFArrayCallBacks cb=kCFTypeArrayCallBacks;cb.release=syntheticArrayRelease;array=CFArrayCreateMutable(kCFAllocatorDefault,0,&cb);
 if(!array){CFRelease(data);return false;}CFArrayAppendValue(array,data);CFRelease(data);
 KMNestedCalibrationChild((uintptr_t)data);KMSetReleaseWatch((uintptr_t)array);CFRelease(array);
 bool ok=KMNestedCalibrationCount()==1&&KMReleaseCount()==1&&KMOuterReleaseReturns()==1;
 KMStopReleaseWatch();KMNestedCalibrationChild(0);return ok;
}
static bool pinnedResourceCode(){
 Dl_info info{};void *symbol=dlsym(RTLD_DEFAULT,"IOAccelDeviceGetConfig");
 if(!symbol||!dladdr(symbol,&info)||!info.dli_fname||strcmp(info.dli_fname,"/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator")||!info.dli_fbase)return false;
 struct Code {uintptr_t offset;size_t length;const char*sha;};
 const Code codes[]={{0x1c14,181,"4a2716ebd724b52e4c2cab4e345094eab8a0bbb24a5316ee565478d6732f8059"},{0x26a5,216,"17f9d42efe9b91891078eebb6dbe32fd90fd00fcf542079507ec5ba3d4cde3f7"}};
 for(const auto& c:codes){unsigned char b[256],h[32];if(!readBytes((uintptr_t)info.dli_fbase+c.offset,b,c.length))return false;CC_SHA256(b,(CC_LONG)c.length,h);char text[65]{};const char *digits="0123456789abcdef";for(unsigned i=0;i<32;i++){text[2*i]=digits[h[i]>>4];text[2*i+1]=digits[h[i]&15];}if(strcmp(text,c.sha))return false;}
 return true;
}
static int covers(uintptr_t p,size_t length){
 if(!p||!length||p>UINTPTR_MAX-(length-1))return 0;mach_vm_address_t start=p;mach_vm_size_t size=0;
 vm_region_basic_info_data_64_t info{};mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;mach_port_t obj=MACH_PORT_NULL;
 kern_return_t kr=mach_vm_region(mach_task_self(),&start,&size,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&obj);if(obj)mach_port_deallocate(mach_task_self(),obj);
 if(kr==KERN_INVALID_ADDRESS)return 0;if(kr!=KERN_SUCCESS)return -1;
 return start<=p&&p-start<size&&length<=size-(p-start)?1:0;
}
static NSDictionary *coverage(const Snapshot &s){
 bool ok=s.valid;int first=ok?covers(s.fields[0],0x104):-1;int second=ok?covers(s.fields[1],0x1c):-1;
 return @{ @"snapshot_valid":@(ok), @"first_nonzero":@(ok&&s.fields[0]!=0), @"second_nonzero":@(ok&&s.fields[1]!=0), @"first_range_covered":@(first), @"second_range_covered":@(second)};
}
static bool releaseCalibration(){
 UInt8 value=0x37;CFDataRef data=CFDataCreate(kCFAllocatorDefault,&value,1);if(!data)return false;
 KMSetReleaseWatch((uintptr_t)data);CFRelease(data);return KMStopReleaseWatch()==1;
}
static bool weakCalibration(){
 __weak NSObject *weak=nil;@autoreleasepool {NSObject *object=[NSObject new];weak=object;object=nil;}
 return weak==nil;
}
struct ReleaseCalibration {bool pinned=false, typeMatches=false, balanced=false;unsigned intercepted=0,entries=0;};
static ReleaseCalibration releaseCase;
static void calibrateRealResource(uintptr_t resource){
 using TypeProc=CFTypeID(*)();using ReleaseProc=void(*)(void*);
 void *tp=dlsym(RTLD_DEFAULT,"IOAccelResourceGetTypeID");Dl_info t{};
 if(!tp||!dladdr(tp,&t)||!t.dli_fname||strcmp(t.dli_fname,"/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator")||!t.dli_fbase||(uintptr_t)tp-(uintptr_t)t.dli_fbase!=0x4af0)return;void *rp=(void*)((uintptr_t)t.dli_fbase+0x268e);
 struct Code {void*ptr;size_t len;const char*sha;};const Code cases[]={{tp,38,"41df086ce4cd848474a10520ad9950691b9c63476f55e25f3ddb51df1db4ebce"},{rp,23,"8ac888dddadbff213f95ce447bbf2a0189e2fc7f41b3132d01cf9b5f471153a0"}};
 for(auto &c:cases){unsigned char buf[64],h[32];char hex[65]{};const char*d="0123456789abcdef";if(!readBytes((uintptr_t)c.ptr,buf,c.len))return;CC_SHA256(buf,(CC_LONG)c.len,h);for(unsigned i=0;i<32;i++){hex[2*i]=d[h[i]>>4];hex[2*i+1]=d[h[i]&15];}if(strcmp(hex,c.sha))return;}
 releaseCase.pinned=true;CFTypeID expected=((TypeProc)tp)();CFTypeRef value=(CFTypeRef)resource;releaseCase.typeMatches=expected&&CFGetTypeID(value)==expected;if(!releaseCase.typeMatches)return;
 CFTypeRef extra=CFRetain(value);if(extra!=value)return;KMSetReleaseWatch(resource);IOAccelResourceRelease((void*)value);releaseCase.entries=KMResourceEntryCount();releaseCase.intercepted=KMStopReleaseWatch();releaseCase.balanced=true;
}
static bool calibration(){
 mach_vm_address_t p=0;const mach_vm_size_t size=4096;if(mach_vm_allocate(mach_task_self(),&p,size,VM_FLAGS_ANYWHERE)!=KERN_SUCCESS)return false;
 bool ok=covers(p,size)==1&&covers(0,4)==0;bool deallocated=mach_vm_deallocate(mach_task_self(),p,size)==KERN_SUCCESS;return ok&&deallocated&&covers(p,size)==0;
}
static NSDictionary *resourceIdentity(id object,bool coexist){
 Method m=class_getInstanceMethod(object_getClass(object),sel_registerName("resourceRef"));Ivar iv=class_getInstanceVariable(object_getClass(object),"_res");
 if(!m||!iv)return @{@"status":@"NO_METADATA"};
 const char *type=method_getTypeEncoding(m),*ivarType=ivar_getTypeEncoding(iv);uintptr_t imp=(uintptr_t)method_getImplementation(m);Dl_info di{};unsigned char bytes[18],digest[32];
 bool pin=type&&!strcmp(type,"^{__IOAccelResource=}16@0:8")&&ivarType&&strstr(ivarType,"\"resourceRef\"^{__IOAccelResource}")&&ivar_getOffset(iv)==24&&dladdr((void*)imp,&di)&&di.dli_fname&&!strcmp(di.dli_fname,"/System/Library/Frameworks/Metal.framework/Versions/A/MetalOld.dylib")&&di.dli_fbase&&imp-(uintptr_t)di.dli_fbase==0xcad3f&&readBytes(imp,bytes,sizeof bytes);
 char hex[65]{};if(pin){CC_SHA256(bytes,sizeof bytes,digest);const char*h="0123456789abcdef";for(unsigned i=0;i<32;i++){hex[2*i]=h[digest[i]>>4];hex[2*i+1]=h[digest[i]&15];}pin=!strcmp(hex,"348a6081407e4ff380a668ae3d6d4f67087965110af9380e090f87f83cd4d982");}
 int32_t disp=0;uintptr_t ivarOffset=0,resource=0;if(pin){memcpy(&disp,bytes+7,4);pin=readBytes(imp+11+(intptr_t)disp,&ivarOffset,sizeof ivarOffset)&&ivarOffset==24&&class_getInstanceSize(object_getClass(object))>=ivarOffset+0x78;}
 bool read=pin&&readBytes((uintptr_t)(__bridge void*)object+ivarOffset+0x70,&resource,sizeof resource);
 bool matching=read&&resource&&KMResourceSharedMatch(resource);
 Class actual=object_getClass(object);Method actualDealloc=class_getInstanceMethod(actual,sel_registerName("dealloc"));IMP selectedImp=actualDealloc?method_getImplementation(actualDealloc):nullptr;Dl_info selectedInfo{};bool ours=selectedImp==(IMP)&hookBuffer||selectedImp==(IMP)&hookResource||selectedImp==(IMP)&hookNV;bool selectedMetal=selectedImp&&dladdr((void*)selectedImp,&selectedInfo)&&selectedInfo.dli_fname&&selectedInfo.dli_fbase&&!strcmp(selectedInfo.dli_fname,"/System/Library/Frameworks/Metal.framework/Versions/A/MetalOld.dylib");uintptr_t selectedOffset=selectedImp&&selectedInfo.dli_fbase?(uintptr_t)selectedImp-(uintptr_t)selectedInfo.dli_fbase:0;
 const char*selectedImage=selectedInfo.dli_fname?strrchr(selectedInfo.dli_fname,'/'):nullptr;selectedImage=selectedImage?selectedImage+1:"unknown";Class super=class_getSuperclass(actual);const char*superName=super?class_getName(super):"unknown";
 unsigned char selectedBytes[32],selectedDigest[32];char selectedHash[65]{};bool selectedRead=selectedImp&&readBytes((uintptr_t)selectedImp,selectedBytes,sizeof selectedBytes);if(selectedRead){CC_SHA256(selectedBytes,sizeof selectedBytes,selectedDigest);const char*d="0123456789abcdef";for(unsigned i=0;i<32;i++){selectedHash[2*i]=d[selectedDigest[i]>>4];selectedHash[2*i+1]=d[selectedDigest[i]&15];}}
 if(snapshotCount<2){unsigned n=snapshotCount++;Snapshot &snap=snapshots[n];snap.valid=matching&&pinnedResourceCode()&&readBytes(resource+0x48,snap.fields,sizeof snap.fields);if(n==0&&snap.valid){watchedObject.store((uintptr_t)(__bridge void*)object);watchedResourceObject.store(resource);calibrateRealResource(resource);KMSetReleaseWatch(resource);}}bool rejectedNull=!KMResourceContextProbe(0);bool requested=coexist&&matching&&rejectedNull;bool contextStarted=requested&&KMResourceContextProbe(resource);bool after=matching&&KMResourceSharedMatch(resource);
 return @{@"actual_class":@(class_getName(actual)),@"actual_superclass":@(superName),@"selected_image":@(selectedImage),@"selected_bytes_sha256":@(selectedHash),@"selected_bytes_read":@(selectedRead),@"selected_dealloc_is_hook":@(ours),@"selected_dealloc_in_metal":@(selectedMetal),@"selected_dealloc_offset":@(selectedOffset),@"null_context_rejected":@(rejectedNull),@"context_requested":@(requested),@"context_started":@(contextStarted),@"resource_shared_after":@(after),@"status":pin?@"PINNED":@"PROFILE_REFUSED",@"getter_sha256":@(hex),@"ivar_offset":@(ivarOffset),@"resource_slot_offset":@(ivarOffset+0x70),@"slot_read":@(read),@"resource_nonnull":@(read&&resource!=0),@"resource_shared_matches":@(matching),@"negative_null_rejected":@(!KMResourceSharedMatch(0)),@"getter_called":@NO};
}
static bool executeGPU(id<MTLDevice> device,id<MTLBuffer> __strong *inputRef){
 bool ok=false;@autoreleasepool {
 __unsafe_unretained id<MTLBuffer> input=*inputRef;__weak id<MTLBuffer> weak=input;
 NSString *source=@"#include <metal_stdlib>\nusing namespace metal;\nkernel void witness(device const uchar *s [[buffer(0)]],device uint *d [[buffer(1)]],constant uint &salt [[buffer(2)]],uint i [[thread_position_in_grid]]){d[i]=uint(s[i])*3u+i+salt;}\n";
 NSError *error=nil;id<MTLLibrary> lib=[device newLibraryWithSource:source options:nil error:&error];id<MTLFunction> fn=lib?[lib newFunctionWithName:@"witness"]:nil;id<MTLComputePipelineState> pipe=fn?[device newComputePipelineStateWithFunction:fn error:&error]:nil;
 id<MTLBuffer> outA=[device newBufferWithLength:4096*sizeof(uint32_t) options:MTLResourceStorageModeShared],outB=[device newBufferWithLength:4096*sizeof(uint32_t) options:MTLResourceStorageModeShared];
 id<MTLCommandQueue> queueA=[device newCommandQueue],queueB=[device newCommandQueue];id<MTLCommandBuffer> cbA=queueA?[queueA commandBuffer]:nil,cbB=queueB?[queueB commandBuffer]:nil;
 if(!pipe||!outA||!outB||!outA.contents||!outB.contents||!cbA||!cbB||queueA==queueB)return false;
 uint32_t *a=(uint32_t*)outA.contents,*b=(uint32_t*)outB.contents;for(unsigned i=0;i<4096;i++){a[i]=b[i]=0xa5a5a5a5u;}
 id<MTLCommandBuffer> buffers[2]={cbA,cbB};id<MTLBuffer> outputs[2]={outA,outB};
 for(unsigned q=0;q<2;q++){id<MTLComputeCommandEncoder> enc=[buffers[q] computeCommandEncoder];if(!enc)return false;uint32_t salt=q?0x1234u:0u;
  [enc setComputePipelineState:pipe];[enc setBuffer:input offset:0 atIndex:0];[enc setBuffer:outputs[q] offset:0 atIndex:1];[enc setBytes:&salt length:sizeof salt atIndex:2];[enc dispatchThreadgroups:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];gpuDispatches++;[enc endEncoding];
  [buffers[q] addCompletedHandler:^(id<MTLCommandBuffer> finished){gpuHandlerStatus.store((unsigned)finished.status);gpuHandlerCount++;}];
 }
 *inputRef=nil;gpuPrecommitWeakAlive=weak!=nil;gpuPrecommitCallbacks=noCopyDeallocCalls.load();if(!gpuPrecommitWeakAlive||gpuPrecommitCallbacks)return false;
 [cbA commit];[cbB commit];[cbA waitUntilCompleted];gpuSecondAtFirstWait=(unsigned)cbB.status;gpuAfterFirstCallbacks=noCopyDeallocCalls.load();[cbB waitUntilCompleted];gpuStatus=(unsigned)cbA.status;gpuSecondStatus=(unsigned)cbB.status;
 gpuWords=[NSMutableArray arrayWithCapacity:8192];for(unsigned q=0;q<2;q++)for(unsigned i=0;i<4096;i++){uint32_t got=q?b[i]:a[i],want=((i*13+7)&255)*3+i+(q?0x1234u:0u);if(got!=want)gpuMismatches++;[gpuWords addObject:@(got)];}
 ok=gpuStatus==MTLCommandBufferStatusCompleted&&gpuSecondStatus==MTLCommandBufferStatusCompleted&&gpuMismatches==0&&gpuAfterFirstCallbacks==0;
 }
 gpuCompleted.store(ok);auto decision=raceGate.result(ok);if(decision==kepler_witness::Decision::deliver&&deliverWitness())gpuDeferredApplied++;return ok;
}
__attribute__((noinline)) static NSDictionary *makeCandidate(id<MTLDevice> device,bool hold,bool nocopy,id<MTLBuffer> __weak *weakOut,id<MTLBuffer> __strong *holdOut,NSDictionary * __strong *beforeOut,bool *okOut){
 @autoreleasepool {
  void *allocation=nullptr;size_t count=nocopy?4096:4194304;__attribute__((objc_precise_lifetime)) id<MTLBuffer> candidate=nil;
  if(nocopy){mach_vm_address_t address=0;long page=sysconf(_SC_PAGESIZE);if(page<=0||count%(size_t)page||mach_vm_allocate(mach_task_self(),&address,count,VM_FLAGS_ANYWHERE)!=KERN_SUCCESS){*okOut=false;return @{};}allocation=(void*)(uintptr_t)address;void*expected=allocation;
   clientState={ (uintptr_t)expected,count,&covers,&noCopyDeallocCalls,&noCopyBadArgs,&callbackAttempts,&callbackDuplicates,&unapprovedCallbacks,&vmBeforeRelease,&vmAfterRelease,&vmReleaseStatus,&releaseAuthorized,&noCopyFreed,&gpuCompleted };
   heldExpectedBlock=KMClientMakeBlock(&clientState);
   if(!heldExpectedBlock){mach_vm_deallocate(mach_task_self(),address,count);*okOut=false;return @{};}
   expectedBlock.store((uintptr_t)(__bridge void*)heldExpectedBlock);
   candidate=[device newBufferWithBytesNoCopy:allocation length:count options:MTLResourceStorageModeShared deallocator:heldExpectedBlock];
   if(!candidate){mach_vm_deallocate(mach_task_self(),(mach_vm_address_t)(uintptr_t)allocation,count);return @{};}
   witnessPointer=(uintptr_t)allocation;witnessLength=count;
  }else candidate=[device newBufferWithLength:count options:MTLResourceStorageModeShared];
  if(candidate&&blockIvarPinned){uintptr_t field=0;blockBeforeRead=readBytes((uintptr_t)(__bridge void*)candidate+blockIvarOffset,&field,sizeof field);blockBeforeNonzero=blockBeforeRead&&field;blockBeforeMatches=blockBeforeNonzero&&field==expectedBlock.load();}
  *weakOut=candidate;if(hold)*holdOut=candidate;
  bool ok=candidate&&candidate.contents&&candidate.length==count&&(!nocopy||candidate.contents==allocation);
  if(ok){uint8_t*x=(uint8_t*)candidate.contents;for(size_t i=0;i<count;i++)x[i]=(i*13+7)&255;for(size_t i=0;i<count;i++)if(x[i]!=((i*13+7)&255)){ok=false;break;}}
  NSDictionary *identity=candidate?resourceIdentity(candidate,false):@{};*beforeOut=coverage(snapshots[0]);
  if(gpuRequested)ok=ok&&executeGPU(device,&candidate);
  *okOut=ok;return identity;
 }
}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3||(strcmp(argv[1],"observe")&&strcmp(argv[1],"release")&&strcmp(argv[1],"nocopy")&&strcmp(argv[1],"hold-nocopy")&&strcmp(argv[1],"nocopy-repair")&&strcmp(argv[1],"nocopy-reject")&&strcmp(argv[1],"nocopy-gpu")&&strcmp(argv[1],"nocopy-repair-gpu")&&strcmp(argv[1],"nocopy-reject-gpu")&&strcmp(argv[1],"nocopy-repair-gpu-late"))||!argv[2][0]||strspn(argv[2],"0123456789")!=strlen(argv[2]))return 2;char*end=nullptr;errno=0;uint64_t rid=strtoull(argv[2],&end,10);if(errno||!rid||!end||*end)return 2;
 io_service_t service=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(rid));uint64_t pci=0;bool valid=service&&IOObjectConformsTo(service,"nvAccelerator")&&ancestor(service,&pci);if(service)IOObjectRelease(service);if(!valid)return 3;
 bool control=calibration(),weakControl=weakCalibration(),releaseControl=releaseCalibration(),superControl=superCalibration(),nestedControl=nestedCalibration();KMObserveBegin(rid,false,false);NSArray<id<MTLDevice>>*all=MTLCopyAllDevices();id<MTLDevice>selected=nil;unsigned hits=0;
 for(id<MTLDevice>d in all){io_service_t t=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(d.registryID));uint64_t id=0;bool same=t&&ancestor(t,&id)&&id==pci;if(t)IOObjectRelease(t);if(same){selected=d;hits++;}}
 bool hooksInstalled=installHooks();if(!hooksInstalled)return 6;
 gpuRequested=strstr(argv[1],"-gpu")!=nullptr;bool repairMode=!strcmp(argv[1],"nocopy-repair")||!strcmp(argv[1],"nocopy-repair-gpu")||!strcmp(argv[1],"nocopy-repair-gpu-late"),rejectMode=!strcmp(argv[1],"nocopy-reject")||!strcmp(argv[1],"nocopy-reject-gpu");witnessPolicy=!rejectMode;if(!gpuRequested)(void)raceGate.result(true);KMSetRootAction((repairMode||rejectMode)?&invokeWitness:nullptr);
 bool noCopyMode=!strcmp(argv[1],"nocopy")||!strcmp(argv[1],"hold-nocopy")||repairMode||rejectMode||gpuRequested;bool isControl=!strcmp(argv[1],"observe")||!strcmp(argv[1],"hold-nocopy"),candidateOk=false;__weak id<MTLBuffer> weakA=nil;__attribute__((objc_precise_lifetime)) id<MTLBuffer> held=nil;NSDictionary *beforeA=nil;
 NSDictionary *ida=hits==1?makeCandidate(selected,isControl,noCopyMode,&weakA,&held,&beforeA,&candidateOk):@{};
 if(!strcmp(argv[1],"nocopy-repair-gpu-late")&&noCopyDeallocCalls.load()==1&&heldExpectedBlock){syntheticLateCalls++;heldExpectedBlock((void*)witnessPointer,witnessLength);}
 bool firstGone=weakA==nil;unsigned bufDealloc=bufferDeallocs.load(),resDealloc=resourceDeallocs.load(),fieldMatches=resourceFieldMatches.load(),nvCount=nvDeallocs.load(),branch=branchKnown.load(),candidate=directCandidate.load();bool hooksRestored=restoreHooks();
 NSMutableArray *timeline=[NSMutableArray array];auto started=std::chrono::steady_clock::now();const int milestones[]={0,250,1000,3000};
 for(int milestone:milestones){while(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count()<milestone){CFRunLoopRunInMode(kCFRunLoopDefaultMode,0.01,true);struct timespec pause={0,10000000};nanosleep(&pause,nullptr);}
  long long elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count();
  [timeline addObject:@{@"target_ms":@(milestone),@"elapsed_ms":@(elapsed),@"entry_calls":@(KMResourceEntryCount()),@"metal_callers":@(KMResourceMetalCallerCount()),@"cf_releases":@(KMReleaseCount()),@"deallocator_calls":@(noCopyDeallocCalls.load()),@"bad_args":@(noCopyBadArgs.load()),@"freed":@(noCopyFreed.load())}];
 }
 NSDictionary *afterA=coverage(snapshots[0]);bool holdCorrect=isControl?(held&&held.length==(noCopyMode?4096:4194304)):held==nil;
 bool keeperOk=false;NSDictionary *idb=nil,*beforeB=nil,*observed=nil;
 __weak id<MTLDevice> weakDevice=selected;__weak id<MTLBuffer> weakKeeper=nil;__weak NSObject *weakPoolWitness=nil;bool poolWitnessInside=false;
 @autoreleasepool {
  __autoreleasing NSObject *poolWitness=[NSObject new];weakPoolWitness=poolWitness;poolWitnessInside=(weakPoolWitness!=nil);
  __attribute__((objc_precise_lifetime)) id<MTLBuffer>b=hits==1?[selected newBufferWithLength:4194304 options:MTLResourceStorageModeShared]:nil;
  keeperOk=b&&b.contents&&b.length==4194304;if(keeperOk){uint8_t*y=(uint8_t*)b.contents;for(unsigned i=0;i<4194304;i++)y[i]=(i*17+3)&255;for(unsigned i=0;i<4194304;i++)if(y[i]!=((i*17+3)&255)){keeperOk=false;break;}}
  KMObserveEnd();idb=b?resourceIdentity(b,false):@{};beforeB=coverage(snapshots[1]);observed=KMObserveResults();weakKeeper=b;b=nil;
 }
 bool poolWitnessDrained=(weakPoolWitness==nil);selected=nil;all=nil;
 NSMutableArray *drainTimeline=[NSMutableArray array];auto drainStart=std::chrono::steady_clock::now();const int drainMilestones[]={0,250,1000,3000};
 for(int milestone:drainMilestones){while(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-drainStart).count()<milestone){CFRunLoopRunInMode(kCFRunLoopDefaultMode,0.01,true);struct timespec pause={0,10000000};nanosleep(&pause,nullptr);}
  long long elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-drainStart).count();bool keeperGone=false,deviceGone=false;@autoreleasepool{keeperGone=weakKeeper==nil;deviceGone=weakDevice==nil;}
  [drainTimeline addObject:@{@"target_ms":@(milestone),@"elapsed_ms":@(elapsed),@"entry_calls":@(KMResourceEntryCount()),@"metal_callers":@(KMResourceMetalCallerCount()),@"cf_releases":@(KMReleaseCount()),@"deallocator_calls":@(noCopyDeallocCalls.load()),@"bad_args":@(noCopyBadArgs.load()),@"freed":@(noCopyFreed.load()),@"keeper_weak_nil":@(keeperGone),@"device_weak_nil":@(deviceGone)}];
 }
 unsigned entries=KMResourceEntryCount(),metalEntries=KMResourceMetalCallerCount();unsigned resourceReleases=KMStopReleaseWatch();
 Dl_info rootImage{};unsigned char stub[6]{};int32_t disp=0;uintptr_t bound=0;bool rootImageOk=dladdr((void*)oldNV,&rootImage)&&rootImage.dli_fbase;
 bool rootStubRead=rootImageOk&&readBytes((uintptr_t)rootImage.dli_fbase+0x1876be,stub,sizeof stub);if(rootStubRead)memcpy(&disp,stub+2,4);
 bool rootStubPinned=rootStubRead&&stub[0]==0xff&&stub[1]==0x25&&disp==0x38fbc;
 bool rootBindingRead=rootStubPinned&&readBytes((uintptr_t)rootImage.dli_fbase+0x1876be + 6 +(intptr_t)disp,&bound,sizeof bound);
 bool rootBindingInterposed=rootBindingRead&&bound==KMRootObserverAddress();bool rootBindingOriginal=rootBindingRead&&bound==KMRootOriginalAddress();
 bool snapshotsValid=snapshotCount==2&&snapshots[0].valid&&snapshots[1].valid;
 uintptr_t blockInvoke=0; Dl_info clientImage{};bool clientBound=heldExpectedBlock&&readBytes((uintptr_t)(__bridge void*)heldExpectedBlock+16,&blockInvoke,sizeof blockInvoke)&&blockInvoke&&dladdr((void*)blockInvoke,&clientImage)&&clientImage.dli_fname&&strstr(clientImage.dli_fname,"/libClientCallback.dylib");
 NSDictionary*r=@{@"client_library_bound":@(clientBound),@"client_calls":@(KMClientCalls()),@"client_rejected":@(KMClientRejected()),@"client_status":@(KMClientStatus()),@"vm_before_release":@(vmBeforeRelease.load()),@"vm_after_release":@(vmAfterRelease.load()),@"vm_release_status":@(vmReleaseStatus.load()),@"unapproved_callbacks":@(unapprovedCallbacks.load()),@"root_returned_events":@(rootReturnedEvents.load()),@"callback_attempts":@(callbackAttempts.load()),@"callback_duplicates":@(callbackDuplicates.load()),@"synthetic_late_calls":@(syntheticLateCalls.load()),@"gpu_gate_refusals":@(gpuGateRefusals.load()),@"gpu_deferred_applied":@(gpuDeferredApplied.load()),@"gpu_handler_count":@(gpuHandlerCount.load()),@"gpu_handler_status":@(gpuHandlerStatus.load()),@"gpu_handler_at_refusal":@(gpuHandlerAtRefusal.load()),@"gpu_second_status":@(gpuSecondStatus),@"gpu_second_at_first_wait":@(gpuSecondAtFirstWait),@"gpu_after_first_callbacks":@(gpuAfterFirstCallbacks),@"gpu_precommit_weak_alive":@(gpuPrecommitWeakAlive),@"gpu_precommit_callbacks":@(gpuPrecommitCallbacks),@"gpu_requested":@(gpuRequested),@"gpu_completed":@(gpuCompleted.load()),@"gpu_status":@(gpuStatus),@"gpu_mismatches":@(gpuMismatches),@"gpu_words":gpuWords?:@[],@"repair_attempts":@(KMRepairAttempts()),@"repair_applied":@(KMRepairApplied()),@"repair_rejected":@(KMRepairRejected()),@"witness_only_no_free":@NO,@"release_order":KMReleaseOrder(),@"nested_control":@(nestedControl),@"nested_resource_finalizer_tail":@(KMNestedFinalizerCount()),@"watched_cf_release_returns":@(KMOuterReleaseReturns()),@"root_stub_pinned":@(rootStubPinned),@"root_binding_read":@(rootBindingRead),@"root_binding_interposed":@(rootBindingInterposed),@"root_binding_original":@(rootBindingOriginal),@"root_matches":@(KMRootMatches()),@"block_ivar_pinned":@(blockIvarPinned),@"block_ivar_offset":@(blockIvarOffset),@"block_before_read":@(blockBeforeRead),@"block_before_nonzero":@(blockBeforeNonzero),@"block_before_matches":@(blockBeforeMatches),@"block_dealloc_read":@(blockAtDeallocRead.load()),@"block_dealloc_nonzero":@(blockAtDeallocNonzero.load()),@"block_dealloc_matches":@(blockAtDeallocMatches.load()),@"pool_witness_inside":@(poolWitnessInside),@"pool_witness_drained":@(poolWitnessDrained),@"mode":@(argv[1]),@"timeline":timeline,@"drain_timeline":drainTimeline,@"status":(candidateOk&&keeperOk&&control&&weakControl&&releaseControl&&superControl&&snapshotsValid&&holdCorrect&&hooksInstalled&&hooksRestored&&releaseCase.pinned&&releaseCase.typeMatches&&releaseCase.balanced)?@"OBSERVATION_COMPLETED":@"FAILED",@"pid":@(getpid()),@"registry_id":@(rid),@"pci_id":@(pci),@"metal_candidates":@(hits),@"buffer_CPU_correct":@(candidateOk),@"keeper_CPU_correct_after":@(keeperOk),@"vm_control":@(control),@"weak_control":@(weakControl),@"super_control":@(superControl),@"release_control":@(releaseControl),@"resource_calibration":@{@"pinned":@(releaseCase.pinned),@"type_matches":@(releaseCase.typeMatches),@"balanced":@(releaseCase.balanced),@"intercepted":@(releaseCase.intercepted),@"entries":@(releaseCase.entries)},@"resource_release_calls":@(resourceReleases),@"hooks_installed":@(hooksInstalled),@"hooks_restored":@(hooksRestored),@"nv_dealloc_calls":@(nvCount),@"branch_inputs_read":@(branch),@"root_branch_candidate":@(candidate),@"buffer_dealloc_calls":@(bufDealloc),@"resource_dealloc_calls":@(resDealloc),@"resource_field_matches":@(fieldMatches),@"resource_entry_calls":@(entries),@"metal_caller_matches":@(metalEntries),@"resource_a":ida,@"resource_b":idb,@"before_a":beforeA?:@{},@"hold_correct":@(holdCorrect),@"after_a":afterA,@"before_b":beforeB,@"first_buffer_weak_nil":@(firstGone),@"nocopy_deallocator_calls":@(noCopyDeallocCalls.load()),@"nocopy_deallocator_bad_args":@(noCopyBadArgs.load()),@"nocopy_memory_freed":@(noCopyFreed.load()),@"observation":observed,@"explicit_GPU_dispatches":@(gpuDispatches),@"hardware_video_execution_proved":@NO};
 NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];if(!j)return 4;fwrite(j.bytes,1,j.length,stdout);puts("");return candidateOk&&keeperOk&&control&&weakControl&&releaseControl&&superControl&&snapshotsValid&&holdCorrect&&hooksInstalled&&hooksRestored&&releaseCase.pinned&&releaseCase.typeMatches&&releaseCase.balanced?0:5;
}}
