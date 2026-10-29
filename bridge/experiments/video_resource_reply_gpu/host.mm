// SPDX-License-Identifier: MIT
// Process-local observation of ordinary Metal allocation and IOKit calls.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>
#include <dlfcn.h>
#include <atomic>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <cerrno>
#include <sched.h>
#include <unistd.h>
#include <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach_vm.h>

#if defined(KP_OBSERVER_LIBRARY)
namespace {
constexpr unsigned LIMIT=2048;
struct Event {std::atomic<bool> ready{false}; bool replyValid=false; uintptr_t replyA=0,replyB=0; unsigned phase=0;const char *kind=nullptr;uint32_t port=0,selector=0,status=0,scalarCount=0;uint64_t inSize=0,outSize=0,registry=0;uintptr_t caller=0;};
Event events[LIMIT];std::atomic<unsigned> count{0},dropped{0},phase{0},inflight{0};std::atomic<bool> enabled{false};
struct Scope {bool active;Scope():active(enabled.load(std::memory_order_acquire)){if(active){inflight.fetch_add(1);if(!enabled.load(std::memory_order_acquire)){inflight.fetch_sub(1);active=false;}}}~Scope(){if(active)inflight.fetch_sub(1);}};
void record(const char *kind,void *caller,uint32_t port,uint32_t selector,kern_return_t status,uint32_t scalars,uint64_t inSize,uint64_t outSize,uint64_t registry=0){
    Scope scope;if(!scope.active)return;unsigned i=count.fetch_add(1);if(i>=LIMIT){dropped.fetch_add(1);return;}
    Event &e=events[i];e.kind=kind;e.phase=phase.load();e.caller=(uintptr_t)caller;e.port=port;e.selector=selector;e.status=(uint32_t)status;e.scalarCount=scalars;e.inSize=inSize;e.outSize=outSize;e.registry=registry;e.ready.store(true,std::memory_order_release);
}
kern_return_t watchOpen(io_service_t svc,task_port_t task,uint32_t type,io_connect_t *out){
    void *caller=__builtin_return_address(0);kern_return_t k=IOServiceOpen(svc,task,type,out);uint64_t rid=0;IORegistryEntryGetRegistryEntryID(svc,&rid);
    record("open",caller,k==0 && out?*out:0,type,k,0,0,0,rid);return k;
}
kern_return_t watchClose(io_connect_t port){void *caller=__builtin_return_address(0);kern_return_t k=IOServiceClose(port);record("close",caller,port,0,k,0,0,0);return k;}
kern_return_t watchRelease(io_connect_t port){void *caller=__builtin_return_address(0);kern_return_t k=IOConnectRelease(port);record("release",caller,port,0,k,0,0,0);return k;}
kern_return_t watchMethod(mach_port_t port,uint32_t sel,const uint64_t *in,uint32_t n,const void *s,size_t len,uint64_t *out,uint32_t *on,void *os,size_t *olen){
    void *caller=__builtin_return_address(0);size_t capacity=olen?*olen:0;kern_return_t k=IOConnectCallMethod(port,sel,in,n,s,len,out,on,os,olen);int saved=errno;
    Scope scope;if(scope.active){unsigned i=count.fetch_add(1);if(i>=LIMIT)dropped.fetch_add(1);else{Event &e=events[i];e.kind="method";e.phase=phase.load();e.caller=(uintptr_t)caller;e.port=port;e.selector=sel;e.status=(uint32_t)k;e.scalarCount=n;e.inSize=len;e.outSize=olen?*olen:0;
    Dl_info info{};if(e.phase==4&&k==KERN_SUCCESS&&sel==0&&n==0&&len==168&&os&&olen&&capacity>=89&&*olen==89&&dladdr(caller,&info)&&info.dli_fbase&&info.dli_fname&&!strcmp(info.dli_fname,"/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator")&&(uintptr_t)caller-(uintptr_t)info.dli_fbase==0x2072){memcpy(&e.replyA,(const char*)os+0x10,8);memcpy(&e.replyB,(const char*)os+0x18,8);e.replyValid=e.replyA&&e.replyB;}e.ready.store(true,std::memory_order_release);}}
    errno=saved;return k;
}
kern_return_t watchStruct(mach_port_t port,uint32_t sel,const void *in,size_t n,void *out,size_t *on){
    void *caller=__builtin_return_address(0);kern_return_t k=IOConnectCallStructMethod(port,sel,in,n,out,on);
    record("struct",caller,port,sel,k,0,n,on?*on:0);return k;
}
#define INTERPOSE(replacement, original) __attribute__((used)) static const struct {const void *replacement_;const void *original_;} pair_##original __attribute__((section("__DATA,__interpose")))={(const void*)&replacement,(const void*)&original};
INTERPOSE(watchOpen,IOServiceOpen)
INTERPOSE(watchClose,IOServiceClose)
INTERPOSE(watchRelease,IOConnectRelease)
INTERPOSE(watchMethod,IOConnectCallMethod)
INTERPOSE(watchStruct,IOConnectCallStructMethod)

 } // namespace
extern "C" NSDictionary *KPReplyCompare(uintptr_t a,uintptr_t b) {
 unsigned seen=0,matched=0,wrongMatched=0;for(unsigned i=0;i<std::min(count.load(),LIMIT);i++){Event &e=events[i];if(e.ready.load(std::memory_order_acquire)&&e.replyValid){seen++;matched+=(e.replyA==a&&e.replyB==b);wrongMatched+=(e.replyA==(a^1)&&e.replyB==b);}}
 return @{@"captured_qualified_reply_count":@(seen),@"matching_pairs":@(matched),@"wrong_value_matches":@(wrongMatched),@"raw_addresses_exported":@NO};
}
extern "C" void KPEnable() { enabled.store(true, std::memory_order_release); }
extern "C" void KPPhase(unsigned p) { phase.store(p); }
extern "C" void KPFinish() { enabled.store(false, std::memory_order_release); while(inflight.load()) sched_yield(); }
extern "C" unsigned KPDropped() { return dropped.load(); }
extern "C" unsigned KPInflight() { return inflight.load(); }
extern "C" NSArray *KPEvents() {
    NSMutableArray *observed=[NSMutableArray array]; unsigned n=std::min(count.load(),LIMIT);
    for(unsigned i=0;i<n;i++){Event &e=events[i];if(!e.ready.load(std::memory_order_acquire))continue;Dl_info info{};dladdr((void*)e.caller,&info);
        NSString *image=info.dli_fname?@((const char*)info.dli_fname):@"";NSString *symbol=info.dli_sname?@((const char*)info.dli_sname):@"";
        [observed addObject:@{@"phase":@(e.phase),@"kind":@(e.kind),@"port":@(e.port),@"type_or_selector":@(e.selector),@"status":@(e.status),@"input_scalar_count":@(e.scalarCount),@"input_struct_bytes":@(e.inSize),@"output_struct_bytes":@(e.outSize),@"service_registry_ID":@(e.registry),@"caller_image":image,@"caller_symbol":symbol,@"caller_offset":@(info.dli_fbase?e.caller-(uintptr_t)info.dli_fbase:0)}];}
    return observed;
}
#else
extern "C" NSDictionary *KPReplyCompare(uintptr_t,uintptr_t);
extern "C" void KPEnable();
extern "C" void KPPhase(unsigned);
extern "C" void KPFinish();
extern "C" unsigned KPDropped();
extern "C" unsigned KPInflight();
extern "C" NSArray *KPEvents();
namespace {
bool safeRead(uintptr_t address,void*out,size_t n){mach_vm_size_t got=0;return address&&mach_vm_read_overwrite(mach_task_self(),address,n,(mach_vm_address_t)out,&got)==KERN_SUCCESS&&got==n;}
bool codeHash(uintptr_t addr,size_t size,const char*expected){if(size>512)return false;unsigned char data[512],hash[32];if(!safeRead(addr,data,size))return false;CC_SHA256(data,(CC_LONG)size,hash);char hex[65]{};const char*h="0123456789abcdef";for(int i=0;i<32;i++){hex[2*i]=h[hash[i]>>4];hex[2*i+1]=h[hash[i]&15];}return !strcmp(hex,expected);}
NSDictionary *targetIdentity(id object){
 Method m=class_getInstanceMethod(object_getClass(object),sel_registerName("resourceRef"));Ivar iv=class_getInstanceVariable(object_getClass(object),"_res");
 if(!m||!iv)return @{@"status":@"NO_METADATA"};const char*t=method_getTypeEncoding(m),*it=ivar_getTypeEncoding(iv);uintptr_t imp=(uintptr_t)method_getImplementation(m);Dl_info info{},io{};
 bool pin=t&&!strcmp(t,"^{__IOAccelResource=}16@0:8")&&it&&strstr(it,"\"resourceRef\"^{__IOAccelResource}")&&ivar_getOffset(iv)==24&&dladdr((void*)imp,&info)&&info.dli_fbase&&info.dli_fname&&!strcmp(info.dli_fname,"/System/Library/Frameworks/Metal.framework/Versions/A/MetalOld.dylib")&&imp-(uintptr_t)info.dli_fbase==0xcad3f&&codeHash(imp,18,"348a6081407e4ff380a668ae3d6d4f67087965110af9380e090f87f83cd4d982");
 void*fn=dlsym(RTLD_DEFAULT,"IOAccelResourceCreate");pin=pin&&fn&&dladdr(fn,&io)&&io.dli_fbase&&io.dli_fname&&!strcmp(io.dli_fname,"/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator")&&(uintptr_t)fn-(uintptr_t)io.dli_fbase==0x1fe7&&codeHash((uintptr_t)fn,505,"0796a52f95a0490efa7f909d70e3649f49c361aa7dddb117cc5ac0d94fd4a247");
 int32_t disp=0;uintptr_t ivarOffset=0,resource=0,fields[2]={};unsigned char code[18];
 pin=pin&&safeRead(imp,code,sizeof code);if(pin){memcpy(&disp,code+7,4);pin=safeRead(imp+11+(intptr_t)disp,&ivarOffset,sizeof ivarOffset)&&ivarOffset==24&&class_getInstanceSize(object_getClass(object))>=ivarOffset+0x78;}
 bool read=pin&&safeRead((uintptr_t)(__bridge void*)object+ivarOffset+0x70,&resource,sizeof resource)&&resource&&safeRead(resource+0x48,fields,sizeof fields)&&fields[0]&&fields[1];
 NSDictionary *match=KPReplyCompare(fields[0],fields[1]);return @{@"status":pin?@"PINNED":@"PROFILE_REFUSED",@"resource_fields_read":@(read),@"comparison":match,@"getter_called":@NO};
}
NSDictionary *runTargetCompute(id<MTLDevice>d,id<MTLBuffer>buffer,bool skip){
 @autoreleasepool {NSError*error=nil;NSString*source=@"#include <metal_stdlib>\nusing namespace metal;\nkernel void witness(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) { if(i<4096) out[i]=(i*1664525u)^0x65f3a912u; }\n";
 id<MTLLibrary>lib=[d newLibraryWithSource:source options:nil error:&error];id<MTLFunction>fn=lib?[lib newFunctionWithName:@"witness"]:nil;id<MTLComputePipelineState>ps=fn?[d newComputePipelineStateWithFunction:fn error:&error]:nil;id<MTLCommandQueue>q=ps?[d newCommandQueue]:nil;
 BOOL submitted=NO,complete=NO;if(q&&!skip){id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>enc=cb?[cb computeCommandEncoder]:nil;if(enc){[enc setComputePipelineState:ps];[enc setBuffer:buffer offset:64 atIndex:0];[enc dispatchThreadgroups:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];[enc endEncoding];[cb commit];submitted=YES;[cb waitUntilCompleted];complete=cb.status==MTLCommandBufferStatusCompleted;}}
 const char*path=getenv("KM_BUFFER_CAPTURE");NSData*raw=buffer.contents?[NSData dataWithBytes:buffer.contents length:buffer.length]:nil;BOOL wrote=path&&raw&&[raw writeToFile:@(path) options:0 error:&error];
 return @{@"library":@(lib!=nil),@"pipeline":@(ps!=nil),@"queue":@(q!=nil),@"submitted":@(submitted),@"completed":@(complete),@"skipped":@(skip),@"capture_written":@(wrote),@"count":@4096,@"offset":@64};}
}
uint32_t pciValue(io_registry_entry_t entry,CFStringRef key){CFTypeRef v=IORegistryEntryCreateCFProperty(entry,key,kCFAllocatorDefault,0);uint32_t n=0;if(v&&CFGetTypeID(v)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)v)==4){const UInt8 *p=CFDataGetBytePtr((CFDataRef)v);n=p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}if(v)CFRelease(v);return n;}
bool gpuAncestor(io_registry_entry_t entry,uint64_t *id){if(!entry||IOObjectRetain(entry)!=KERN_SUCCESS)return false;io_registry_entry_t cur=entry;bool found=false;for(unsigned i=0;i<32&&cur;i++){if(IOObjectConformsTo(cur,"IOPCIDevice")){uint64_t rid=0;found=pciValue(cur,CFSTR("vendor-id"))==0x10de&&pciValue(cur,CFSTR("device-id"))==0x1198&&IORegistryEntryGetRegistryEntryID(cur,&rid)==KERN_SUCCESS&&rid;if(found)*id=rid;break;}io_registry_entry_t parent=IO_OBJECT_NULL;kern_return_t k=IORegistryEntryGetParentEntry(cur,kIOServicePlane,&parent);IOObjectRelease(cur);cur=IO_OBJECT_NULL;if(k!=KERN_SUCCESS)break;cur=parent;}if(cur)IOObjectRelease(cur);return found;}
}

int main(int argc,char **argv){@autoreleasepool {
    if(argc!=3||(strcmp(argv[1],"inventory")&&strcmp(argv[1],"control")&&strcmp(argv[1],"buffer")&&strcmp(argv[1],"baseline")&&strcmp(argv[1],"warmed")&&strcmp(argv[1],"large")&&strcmp(argv[1],"purge")&&strcmp(argv[1],"gpu")&&strcmp(argv[1],"no-gpu")))return 2;
    if(!argv[2][0]||strspn(argv[2],"0123456789")!=strlen(argv[2]))return 2;
    errno=0;char *end=nullptr;uint64_t target=strtoull(argv[2],&end,10);if(errno||!end||*end)return 2;
    bool inv=!strcmp(argv[1],"inventory"),control=!strcmp(argv[1],"control"),buffer=!strcmp(argv[1],"buffer"),baseline=!strcmp(argv[1],"baseline"),warmed=!strcmp(argv[1],"warmed"),large=!strcmp(argv[1],"large")||!strcmp(argv[1],"gpu")||!strcmp(argv[1],"no-gpu"),gpu=!strcmp(argv[1],"gpu"),noGPU=!strcmp(argv[1],"no-gpu"),purge=!strcmp(argv[1],"purge");
    if(!inv&&!target)return 2;io_iterator_t it=IO_OBJECT_NULL;io_service_t selected=IO_OBJECT_NULL;
    kern_return_t matching=IOServiceGetMatchingServices(kIOMainPortDefault,IOServiceMatching("nvAccelerator"),&it);unsigned found=0,total=0;uint64_t pci=0;bool truncated=false;NSMutableArray *services=[NSMutableArray array];
    if(!matching){io_service_t svc;while((svc=IOIteratorNext(it))){if(++total>16){truncated=true;IOObjectRelease(svc);break;}io_name_t cls={};uint64_t rid=0,prid=0;kern_return_t cs=IOObjectGetClass(svc,cls),rs=IORegistryEntryGetRegistryEntryID(svc,&rid);bool gpu=gpuAncestor(svc,&prid);bool yes=!cs&&!rs&&!strcmp(cls,"nvAccelerator")&&gpu&&rid==target;[services addObject:@{@"class":@(cls),@"registry_ID":@(rid),@"pci_registry_ID":@(prid),@"class_status":@(cs),@"registry_status":@(rs),@"gpu_ancestor":@(gpu),@"candidate":@(yes)}];if(yes){found++;if(!selected){IOObjectRetain(svc);selected=svc;pci=prid;}}IOObjectRelease(svc);}IOObjectRelease(it);}
    NSMutableDictionary *r=[@{@"mode":@(argv[1]),@"pid":@(getpid()),@"uid":@(getuid()),@"euid":@(geteuid()),@"target":@(target),@"matching_status":@(matching),@"truncated":@(truncated),@"services":services,@"candidate_count":@(found),@"pci_registry_ID":@(pci),@"status":inv?@"INVENTORY_ONLY":@"TARGET_NOT_QUALIFIED",@"explicit_GPU_commands":@0,@"hardware_video_execution_proved":@NO} mutableCopy];
    if(!inv&&!matching&&!truncated&&found==1&&selected){
        KPEnable();KPPhase(1);
        if(control){
            // Null Mach port means these calibration calls cannot reach a driver.
            kern_return_t m=IOConnectCallMethod(MACH_PORT_NULL,0,nullptr,0,nullptr,0,nullptr,nullptr,nullptr,nullptr);
            kern_return_t s=IOConnectCallStructMethod(MACH_PORT_NULL,0,nullptr,0,nullptr,nullptr);
            r[@"null_method_status"]=@(m);r[@"null_struct_status"]=@(s);
            io_connect_t c=IO_OBJECT_NULL;kern_return_t o=IOServiceOpen(selected,mach_task_self(),3,&c);
            r[@"control_open_status"]=@(o);r[@"control_connection"]=@(c!=IO_OBJECT_NULL);
            if(c)r[@"control_close_status"]=@(IOServiceClose(c));
            r[@"status"]=@"CONTROL_RECORDED";
        } else if(buffer||baseline||warmed||large||purge){
            NSArray<id<MTLDevice>> *devices=MTLCopyAllDevices();id<MTLDevice> d=nil;unsigned hits=0;
            for(id<MTLDevice> x in devices){uint64_t mpci=0;io_service_t ms=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(x.registryID));bool same=ms&&gpuAncestor(ms,&mpci)&&mpci==pci;if(ms)IOObjectRelease(ms);if(same){d=x;hits++;r[@"metal_registry_ID"]=@(x.registryID);r[@"metal_pci_registry_ID"]=@(mpci);r[@"metal_name"]=x.name?:@"";}}
            r[@"metal_candidates"]=@(hits);
            if(hits==1 && (baseline||warmed||large||purge)){
                __weak id<MTLBuffer> warmWeak=nil;
                @autoreleasepool {
                    KPPhase(2); __attribute__((objc_precise_lifetime)) id<MTLBuffer> warm=[d newBufferWithLength:4096 options:MTLResourceStorageModeShared];
                    warmWeak=warm; r[@"warm_created"]=@(warm!=nil); KPPhase(3); warm=nil;
                }
                r[@"warm_weak_cleared"]=@(warmWeak==nil);
                __weak id<MTLBuffer> targetWeak=nil;
                @autoreleasepool {
                    KPPhase(4); __attribute__((objc_precise_lifetime)) id<MTLBuffer> targetBuffer=nil;
                    size_t size=(large||purge)?4*1024*1024:4096;
                    if(warmed||large||purge) targetBuffer=[d newBufferWithLength:size options:MTLResourceStorageModeShared];
                    r[@"target_length"]=@(targetBuffer?targetBuffer.length:0);
                    targetWeak=targetBuffer; r[@"target_created"]=@(targetBuffer!=nil); KPPhase(5);
                    bool correct=baseline || (targetBuffer&&targetBuffer.length==size&&targetBuffer.contents);
                    if(!baseline&&correct){uint8_t *v=(uint8_t*)targetBuffer.contents;for(size_t i=0;i<size;i++)v[i]=(uint8_t)((i*13+7)&255);for(size_t i=0;i<size;i++)if(v[i]!=(uint8_t)((i*13+7)&255)){correct=false;break;}}
                    r[@"cpu_bytes_correct"]=@(correct);
                    if(large&&correct)r[@"reply_identity"]=targetIdentity(targetBuffer);
                    if((gpu||noGPU)&&correct)r[@"target_compute"]=runTargetCompute(d,targetBuffer,noGPU);
                    if(purge&&correct){
                        r[@"purge_exception"]=@NO;r[@"cpu_after_purge_checked"]=@NO;r[@"cpu_after_purge_correct"]=@NO;
                        @try {
                            KPPhase(9);r[@"state_initial"]=@([targetBuffer setPurgeableState:MTLPurgeableStateKeepCurrent]);
                            KPPhase(10);r[@"previous_empty"]=@([targetBuffer setPurgeableState:MTLPurgeableStateEmpty]);
                            KPPhase(11);r[@"state_empty"]=@([targetBuffer setPurgeableState:MTLPurgeableStateKeepCurrent]);
                            KPPhase(12);r[@"previous_restore"]=@([targetBuffer setPurgeableState:MTLPurgeableStateNonVolatile]);
                            KPPhase(13);MTLPurgeableState restored=[targetBuffer setPurgeableState:MTLPurgeableStateKeepCurrent];r[@"state_restored"]=@(restored);
                            if(restored==MTLPurgeableStateNonVolatile){
                                KPPhase(14);uint8_t *v=(uint8_t*)targetBuffer.contents;bool valid=v!=nullptr;
                                if(valid){for(size_t i=0;i<size;i++)v[i]=(uint8_t)((i*7+11)&255);for(size_t i=0;i<size;i++)if(v[i]!=(uint8_t)((i*7+11)&255)){valid=false;break;}}
                                r[@"cpu_after_purge_checked"]=@YES;r[@"cpu_after_purge_correct"]=@(valid);
                            }
                        } @catch(NSException *ex) { r[@"purge_exception"]=@YES;r[@"purge_exception_name"]=ex.name?:@""; }
                    }
                    KPPhase(6); targetBuffer=nil;
                }
                KPPhase(7);r[@"target_weak_cleared"]=@(targetWeak==nil);r[@"status"]=@"WARM_COMPARISON_RECORDED";
            }else if(hits==1){
                @autoreleasepool {
                    KPPhase(2);id<MTLBuffer> b=[d newBufferWithLength:4096 options:MTLResourceStorageModeShared];
                    r[@"buffer_created"]=@(b!=nil);bool correct=b&&b.length==4096&&b.contents;
                    if(correct){uint8_t *v=(uint8_t*)b.contents;for(unsigned i=0;i<4096;i++)v[i]=(uint8_t)((i*13+7)&255);for(unsigned i=0;i<4096;i++)if(v[i]!=(uint8_t)((i*13+7)&255)){correct=false;break;}}
                    r[@"cpu_bytes_correct"]=@(correct);KPPhase(3);b=nil;
                }
                KPPhase(4);r[@"status"]=@"BUFFER_RELEASED";
            }else r[@"status"]=@"METAL_DEVICE_NOT_QUALIFIED";
            if(baseline||warmed||large||purge)KPPhase(8);
            d=nil;devices=nil;
        }
        KPFinish();
    }
    if(selected)IOObjectRelease(selected);
    r[@"explicit_GPU_commands"]=@(gpu);r[@"events"]=KPEvents();r[@"dropped"]=@(KPDropped());r[@"observer_inflight_final"]=@(KPInflight());r[@"scalar_values_recorded"]=@NO;r[@"raw_payload_exported"]=@NO;r[@"selected_reply_fields_captured_in_memory"]=@(large&&[r[@"reply_identity"][@"comparison"][@"captured_qualified_reply_count"] unsignedIntValue]>0);
    NSData *json=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];if(!json)return 3;fwrite(json.bytes,1,json.length,stdout);puts("");return 0;
} }

#endif // KP_OBSERVER_LIBRARY
