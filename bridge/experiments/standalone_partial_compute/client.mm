// SPDX-License-Identifier: MIT
// Deliberately imports only public Metal and Foundation APIs.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
struct Params { uint32_t count,seed,r0,r1; };
static void require(bool ok,NSString*s){if(!ok)@throw [NSException exceptionWithName:@"StandaloneComputeWitness" reason:s userInfo:nil];}
static bool complete(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 2;char*end=nullptr;unsigned long scenario=strtoul(argv[3],&end,10);if(!end||*end||(scenario!=0&&scenario!=3))return 2;
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d){fprintf(stderr,"no device\n");return 3;}
 NSString*out=@(argv[2]);NSUInteger n=scenario==3?75:96;MTLSize grid=scenario==3?MTLSizeMake(5,5,3):MTLSizeMake(96,1,1),first=scenario==3?MTLSizeMake(4,4,3):MTLSizeMake(65,1,1),second=scenario==3?MTLSizeMake(5,5,3):MTLSizeMake(32,1,1);
 NSMutableDictionary*result=[@{@"status":@"FAIL",@"scenario":@(scenario),@"pid":@(getpid()),@"device":d.name?:@"",@"registry_id":@(d.registryID),@"device_class":NSStringFromClass(object_getClass(d))}mutableCopy];
 @try{
  NSError*error=nil;id<MTLCommandQueue>q=[d newCommandQueue];require(q!=nil,@"Queue unavailable");result[@"queue_class"]=NSStringFromClass(object_getClass(q));
  id<MTLLibrary>library=[d newLibraryWithFile:@(argv[1]) error:&error];require(library!=nil,error.localizedDescription?:@"Library unavailable");
  id<MTLFunction>f0=[library newFunctionWithName:@"partial_builtin_barrier"],f1=[library newFunctionWithName:@"partial_buffer_stencil"];require(f0&&f1,@"Functions unavailable");
  id<MTLComputePipelineState>p0=[d newComputePipelineStateWithFunction:f0 error:&error],p1=[d newComputePipelineStateWithFunction:f1 error:&error];require(p0&&p1,error.localizedDescription?:@"Pipelines unavailable");
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=4;id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:2 options:MTLResourceStorageModeShared];require(icb!=nil,@"ICB unavailable");
  NSMutableDictionary*buffers=[NSMutableDictionary new];for(NSString*k in @[@"b",@"geo",@"c",@"count1",@"count2"]){NSUInteger bytes=[k hasPrefix:@"count"]?132:n*16+128;id<MTLBuffer>gpu=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate],host=[d newBufferWithLength:bytes options:MTLResourceStorageModeManaged];require(gpu&&host,@"Allocation failed");buffers[k]=gpu;buffers[[k stringByAppendingString:@"Host"]]=host;}
  for(unsigned i=0;i<2;i++){id<MTLBuffer>p=[d newBufferWithLength:1536 options:MTLResourceStorageModeShared];require(p!=nil,@"Parameters failed");memset(p.contents,0xa5,p.length);Params v={(uint32_t)n,i?0x1234u:0x3141u,0,0};memcpy((char*)p.contents+256,&v,sizeof(v));buffers[i?@"p2":@"p1"]=p;}
  auto bind=[&](NSUInteger index,id<MTLComputePipelineState>pipeline,NSArray*names,MTLSize local){id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:index];[c setComputePipelineState:pipeline];for(unsigned i=0;i<4;i++)[c setKernelBuffer:buffers[names[i]] offset:i==3?256:64 atIndex:i];[c concurrentDispatchThreads:grid threadsPerThreadgroup:local];};
  bind(0,p0,@[@"b",@"geo",@"count1",@"p1"],first);bind(1,p1,@[@"b",@"c",@"count2",@"p2"],second);
  id<MTLCommandBuffer>init=[q commandBuffer];id<MTLBlitCommandEncoder>ib=[init blitCommandEncoder];for(NSString*k in @[@"b",@"geo",@"c",@"count1",@"count2"]){id<MTLBuffer>h=buffers[[k stringByAppendingString:@"Host"]];memset(h.contents,0xa5,h.length);if([k hasPrefix:@"count"])memset((char*)h.contents+64,0,4);[h didModifyRange:NSMakeRange(0,h.length)];[ib copyFromBuffer:h sourceOffset:0 toBuffer:buffers[k] destinationOffset:0 size:h.length];}[ib endEncoding];require(complete(init),@"Initialization failed");
  auto save=[&](NSString*prefix){id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];for(NSString*k in @[@"b",@"geo",@"c",@"count1",@"count2"]){id<MTLBuffer>h=buffers[[k stringByAppendingString:@"Host"]];[b copyFromBuffer:buffers[k] sourceOffset:0 toBuffer:h destinationOffset:0 size:h.length];[b synchronizeResource:h];}[b endEncoding];require(complete(cb),@"Readback failed");for(NSString*k in @[@"b",@"geo",@"c",@"count1",@"count2"]){id<MTLBuffer>h=buffers[[k stringByAppendingString:@"Host"]];require([[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:[prefix stringByAppendingFormat:@".%@.bin",k]] atomically:YES],@"Write failed");}};
  save(@"before");id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];require(cb&&e,@"Compute encoder unavailable");result[@"command_buffer_class"]=NSStringFromClass(object_getClass(cb));result[@"compute_encoder_class"]=NSStringFromClass(object_getClass(e));[e executeCommandsInBuffer:icb withRange:NSMakeRange(0,2)];[e endEncoding];require(complete(cb),@"Compute submission failed");save(@"after");result[@"command_status"]=@(cb.status);result[@"status"]=@"PASS";
 }@catch(NSException*x){result[@"failure"]=x.reason?:@"";}
 NSData*j=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return [result[@"status"]isEqual:@"PASS"]?0:7;
}}
