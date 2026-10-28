// SPDX-License-Identifier: MIT
// Isolated proof of an instance-local command-buffer revocation. Not a runtime patch.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <IOKit/IOKitLib.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include <unistd.h>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <cstdlib>
static constexpr uint32_t Count=4096,Guard=16,Sentinel=0xa5f0c3d2u,Native=0xdecafbad,Reuse=0x13579bdf;
static NSString *const Source=@"#include <metal_stdlib>\nusing namespace metal;\nkernel void fill(device uint *p [[buffer(0)]],constant uint& value [[buffer(1)]],uint i [[thread_position_in_grid]]){if(i<4096)p[i]=value^i;}\n";
static uint32_t prop(io_registry_entry_t e,CFStringRef key){CFTypeRef x=IORegistryEntryCreateCFProperty(e,key,kCFAllocatorDefault,0);uint32_t n=0;if(x&&CFGetTypeID(x)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)x)==4){const UInt8*p=CFDataGetBytePtr((CFDataRef)x);n=p[0]|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;}if(x)CFRelease(x);return n;}
static bool ancestor(io_registry_entry_t e,uint64_t *id){if(!e||IOObjectRetain(e)!=KERN_SUCCESS)return false;io_registry_entry_t cur=e;bool found=false;for(unsigned k=0;k<32&&cur;k++){if(IOObjectConformsTo(cur,"IOPCIDevice")){uint64_t rid=0;found=prop(cur,CFSTR("vendor-id"))==0x10de&&prop(cur,CFSTR("device-id"))==0x1198&&IORegistryEntryGetRegistryEntryID(cur,&rid)==KERN_SUCCESS&&rid;if(found)*id=rid;break;}io_registry_entry_t parent=0;int s=IORegistryEntryGetParentEntry(cur,kIOServicePlane,&parent);IOObjectRelease(cur);cur=0;if(s!=KERN_SUCCESS)break;cur=parent;}if(cur)IOObjectRelease(cur);return found;}
static void revoked(id,SEL selector){[NSException raise:@"KeplerRevokedCommandBuffer" format:@"%@ refused after explicit revocation",NSStringFromSelector(selector)];}
static bool refuse(id<MTLCommandBuffer> cb){
 Class original=object_getClass(cb);if(!cb||original!=objc_getClass("NVMTLCommandBuffer")||class_getInstanceSize(original)!=656||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)return false;
 Method commit=class_getInstanceMethod(original,@selector(commit)),enqueue=class_getInstanceMethod(original,@selector(enqueue));if(!commit||!enqueue)return false;
 const char *a=method_getTypeEncoding(commit),*b=method_getTypeEncoding(enqueue);if(!a||!b||strcmp(a,"v16@0:8")||strcmp(b,"v16@0:8"))return false;
 NSString*name=[@"KPRevokedWitness_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@""]];Class dynamic=objc_allocateClassPair(original,name.UTF8String,0);if(!dynamic)return false;
 if(!class_addMethod(dynamic,@selector(commit),(IMP)revoked,a)||!class_addMethod(dynamic,@selector(enqueue),(IMP)revoked,b)){objc_disposeClassPair(dynamic);return false;}
 objc_registerClassPair(dynamic);if(class_getInstanceSize(dynamic)!=class_getInstanceSize(original))return false;object_setClass(cb,dynamic);return object_getClass(cb)==dynamic;
}
static bool blocked(id<MTLCommandBuffer> cb,SEL selector){@try{typedef void(*F)(id,SEL);((F)objc_msgSend)(cb,selector);}@catch(NSException*e){return [e.name isEqual:@"KeplerRevokedCommandBuffer"];}return false;}
static bool encode(id<MTLCommandBuffer>cb,id<MTLComputePipelineState>pipeline,id<MTLBuffer>buffer,uint32_t value){id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];if(!e)return false;[e setComputePipelineState:pipeline];[e setBuffer:buffer offset:Guard*sizeof(uint32_t) atIndex:0];[e setBytes:&value length:4 atIndex:1];[e dispatchThreadgroups:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];[e endEncoding];return true;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4||(strcmp(argv[1],"native")&&strcmp(argv[1],"revoked")&&strcmp(argv[1],"revoked-negative"))||!argv[2][0]||strspn(argv[2],"0123456789")!=strlen(argv[2]))return 2;char*end=nullptr;errno=0;uint64_t rid=strtoull(argv[2],&end,10);if(errno||!rid||!end||*end)return 2;
 io_service_t svc=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(rid));uint64_t pci=0;bool target=svc&&IOObjectConformsTo(svc,"nvAccelerator")&&ancestor(svc,&pci);if(svc)IOObjectRelease(svc);if(!target)return 3;
 NSArray<id<MTLDevice>>*all=MTLCopyAllDevices();id<MTLDevice>device=nil;unsigned hits=0;for(id<MTLDevice>d in all){io_service_t s=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(d.registryID));uint64_t id=0;bool same=s&&ancestor(s,&id)&&id==pci;if(s)IOObjectRelease(s);if(same){device=d;hits++;}}
 NSError*err=nil;id<MTLLibrary>lib=hits==1?[device newLibraryWithSource:Source options:nil error:&err]:nil;id<MTLFunction>fn=[lib newFunctionWithName:@"fill"];id<MTLComputePipelineState>pipe=fn?[device newComputePipelineStateWithFunction:fn error:&err]:nil;id<MTLCommandQueue>q=pipe?[device newCommandQueue]:nil;id<MTLBuffer>b=q?[device newBufferWithLength:(Count+Guard*2)*4 options:MTLResourceStorageModeShared]:nil;if(!b||!b.contents)return 4;
 uint32_t*v=(uint32_t*)b.contents;for(unsigned i=0;i<Count+2*Guard;i++)v[i]=Sentinel;bool native=!strcmp(argv[1],"native"),negative=!strcmp(argv[1],"revoked-negative");
 id<MTLCommandBuffer> stale=[q commandBuffer];if(!stale||!encode(stale,pipe,b,Native))return 5;bool installed=false,commitBlocked=false,enqueueBlocked=false,secondBlocked=false;int initialStatus=(int)stale.status;bool initialUntouched=true;for(unsigned i=0;i<Count+Guard*2;i++)initialUntouched&=v[i]==Sentinel;unsigned dispatches=0;bool completed=false,lateRefused=false;
 if(native){[stale commit];dispatches++;[stale waitUntilCompleted];completed=stale.status==MTLCommandBufferStatusCompleted;lateRefused=!refuse(stale);}
 else {installed=refuse(stale);if(installed){commitBlocked=blocked(stale,@selector(commit));enqueueBlocked=blocked(stale,@selector(enqueue));}int after=(int)stale.status;if(after!=MTLCommandBufferStatusNotEnqueued)return 6;
  id<MTLCommandBuffer>next=[q commandBuffer];if(!next)return 7;if(!negative&&!encode(next,pipe,b,Reuse))return 8;[next commit];if(!negative)dispatches++;[next waitUntilCompleted];completed=next.status==MTLCommandBufferStatusCompleted;lateRefused=!refuse(next);if(installed)secondBlocked=blocked(stale,@selector(commit));}
 unsigned errors=0,guards=0;for(unsigned i=0;i<Count;i++){uint32_t expected=negative?Sentinel:((native?Native:Reuse)^i);errors+=v[Guard+i]!=expected;}for(unsigned i=0;i<Guard;i++){guards+=v[i]!=Sentinel;guards+=v[Guard+Count+i]!=Sentinel;}
 NSData*data=[NSData dataWithBytes:v length:(Count+Guard*2)*4];BOOL written=[data writeToFile:[@(argv[3]) stringByAppendingPathComponent:@"capture.bin"] atomically:NO];
 NSDictionary*r=@{@"mode":@(argv[1]),@"pid":@(getpid()),@"registry_id":@(rid),@"device_candidates":@(hits),@"native_class":@"NVMTLCommandBuffer",@"initial_status":@(initialStatus),@"initial_untouched":@(initialUntouched),@"guard_installed":@(installed),@"commit_blocked":@(commitBlocked),@"enqueue_blocked":@(enqueueBlocked),@"second_commit_blocked":@(secondBlocked),@"late_revoke_refused":@(lateRefused),@"stale_final_status":@((int)stale.status),@"completed":@(completed),@"dispatches":@(dispatches),@"errors":@(errors),@"guard_errors":@(guards),@"written":@(written),@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return (completed&&written&&!errors&&!guards)?0:9;
}}
