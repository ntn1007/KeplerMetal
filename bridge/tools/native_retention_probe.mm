// Weak-reference lifetime observations; encoded command buffers never committed.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#include <cstdio>
static NSString*hash(NSData*d){unsigned char digest[32];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*s=[NSMutableString new];for(unsigned char x:digest)[s appendFormat:@"%02x",x];return s;}
static id<MTLBuffer>queueQMD(id<MTLCommandQueue>q){Ivar v=class_getInstanceVariable(object_getClass(q),"_queue");if(!v||ivar_getOffset(v)!=680)return nil;uintptr_t cpp=0,p=0;memcpy(&cpp,(const char*)(__bridge const void*)q+680,8);mach_vm_size_t n=0;if(mach_vm_read_overwrite(mach_task_self(),cpp+16,8,(mach_vm_address_t)&p,&n)!=KERN_SUCCESS||n!=8||!p)return nil;id o=(__bridge id)(void*)p;return [o isKindOfClass:objc_getClass("NVMTLBuffer")]?o:nil;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=2)return 1;NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
 if(![hash(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name containsString:@"880M"]){d=x;break;}if(!d)return 3;
 NSError*error=nil;id<MTLLibrary>library=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];id<MTLComputePipelineState>pipe=[d newComputePipelineStateWithFunction:[library newFunctionWithName:@"consume_grid"] error:&error];if(!pipe)return 4;
 NSMutableArray*rows=[NSMutableArray new];
 for(unsigned mode=0;mode<2;mode++)for(unsigned iteration=0;iteration<3;iteration++){
  __weak id<MTLCommandQueue>wq=nil;__weak id<MTLBuffer>wqmd=nil,wout=nil,wcounter=nil,wargs=nil,wparams=nil;
  id<MTLCommandBuffer>held=nil;uintptr_t qAddress=0,qmdAddress=0;bool retainFlag=false;
  @autoreleasepool{
   id<MTLCommandQueue>q=[d newCommandQueue];held=mode?[q commandBufferWithUnretainedReferences]:[q commandBuffer];retainFlag=held.retainedReferences;
   id<MTLBuffer>qmd=queueQMD(q),out=[d newBufferWithLength:10496 options:MTLResourceStorageModePrivate],counter=[d newBufferWithLength:512 options:MTLResourceStorageModePrivate],args=[d newBufferWithLength:512 options:MTLResourceStorageModePrivate];
   uint32_t p[4]={0x1234,3,32,640};id<MTLBuffer>params=[d newBufferWithBytes:p length:16 options:MTLResourceStorageModeShared];if(!qmd||qmd.length!=4096||!out||!counter||!args||!params)return 5;
   wq=q;wqmd=qmd;wout=out;wcounter=counter;wargs=args;wparams=params;qAddress=(uintptr_t)(__bridge const void*)q;qmdAddress=(uintptr_t)(__bridge const void*)qmd;
   id<MTLComputeCommandEncoder>e=[held computeCommandEncoder];[e setComputePipelineState:pipe];[e setBuffer:out offset:64 atIndex:0];[e setBuffer:counter offset:64 atIndex:1];[e setBuffer:params offset:0 atIndex:2];[e dispatchThreadgroupsWithIndirectBuffer:args indirectBufferOffset:64 threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];
  }
  NSDictionary*whileHeld=nil;
  @autoreleasepool{whileHeld=@{@"queue":@(wq!=nil),@"queue_QMD":@(wqmd!=nil),@"output":@(wout!=nil),@"counter":@(wcounter!=nil),@"args":@(wargs!=nil),@"params":@(wparams!=nil)};}
  NSUInteger status=held.status;held=nil;NSDictionary*afterRelease=nil;
  @autoreleasepool{afterRelease=@{@"queue":@(wq!=nil),@"queue_QMD":@(wqmd!=nil),@"output":@(wout!=nil),@"counter":@(wcounter!=nil),@"args":@(wargs!=nil),@"params":@(wparams!=nil)};}
  [rows addObject:@{@"mode":mode?@"unretained_negative_control":@"retained",@"iteration":@(iteration),@"retained_references":@(retainFlag),@"queue_address":@(qAddress),@"QMD_object_address":@(qmdAddress),@"while_command_buffer_held":whileHeld,@"after_command_buffer_released":afterRelease,@"status_before_release":@(status)}];
 }
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"driver_SHA256":hash(driver),@"records":rows,@"GPU_dispatch":@NO,@"committed":@NO,@"scope":@"Autorelease pools drained, only command buffer held. Weak observations before/after its release; unretained control never submitted. No reads of released memory, private calls or writes."};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
