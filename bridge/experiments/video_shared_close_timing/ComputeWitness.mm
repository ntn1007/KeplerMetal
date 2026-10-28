// SPDX-License-Identifier: MIT
#import "ComputeWitness.h"
#include <cstdint>
static constexpr uint32_t Count=4096, Guard=16, Sentinel=0xa5f0c3d2u;
static NSString *const Source=@"#include <metal_stdlib>\nusing namespace metal;\nkernel void witness(device uint *out [[buffer(0)]], constant uint &seed [[buffer(1)]], uint i [[thread_position_in_grid]]) { if(i < 4096) out[i]=(i*1664525u)^seed; }\n";
ComputeResult runCompute(id<MTLDevice> device,NSString *directory,NSString *phase,uint32_t seed,bool skip){
 ComputeResult result{};result.attempted=true;NSError *error=nil;
 id<MTLLibrary> library=[device newLibraryWithSource:Source options:nil error:&error];
 result.library=library!=nil;if(!library)return result;
 id<MTLFunction> fn=[library newFunctionWithName:@"witness"];
 result.function=fn!=nil;id<MTLComputePipelineState> state=fn?[device newComputePipelineStateWithFunction:fn error:&error]:nil;
 result.pipeline=state!=nil;id<MTLCommandQueue> queue=state?[device newCommandQueue]:nil;
 result.queue=queue!=nil;id<MTLBuffer> buffer=queue?[device newBufferWithLength:(Count+Guard*2)*sizeof(uint32_t) options:MTLResourceStorageModeShared]:nil;
 result.buffer=buffer!=nil;if(buffer){
  uint32_t *values=(uint32_t*)buffer.contents;for(uint32_t i=0;i<Count+Guard*2;i++)values[i]=Sentinel;
  if(!skip){
   id<MTLCommandBuffer> command=[queue commandBuffer];id<MTLComputeCommandEncoder> enc=command?[command computeCommandEncoder]:nil;
   if(enc){[enc setComputePipelineState:state];[enc setBuffer:buffer offset:Guard*sizeof(uint32_t) atIndex:0];[enc setBytes:&seed length:sizeof(seed) atIndex:1];[enc dispatchThreadgroups:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];[enc endEncoding];[command commit];result.submitted=true;[command waitUntilCompleted];result.completed=command.status==MTLCommandBufferStatusCompleted;}
  }
  for(uint32_t i=0;i<Count;i++){uint32_t expected=skip?Sentinel:(i*1664525u)^seed;if(values[Guard+i]!=expected)result.errors++;}
  for(uint32_t i=0;i<Guard;i++){if(values[i]!=Sentinel)result.guardErrors++;if(values[Guard+Count+i]!=Sentinel)result.guardErrors++;}
  NSData *data=[NSData dataWithBytes:values length:(Count+Guard*2)*sizeof(uint32_t)];
  result.written=[data writeToFile:[directory stringByAppendingPathComponent:[phase stringByAppendingString:@"-compute.bin"]] options:0 error:&error];
 }
 if(buffer)[buffer release];if(queue)[queue release];if(state)[state release];if(fn)[fn release];[library release];return result;
}
NSDictionary *computeDict(const ComputeResult &r){return @{@"attempted":@(r.attempted),@"library":@(r.library),@"function":@(r.function),@"pipeline":@(r.pipeline),@"queue":@(r.queue),@"buffer":@(r.buffer),@"submitted":@(r.submitted),@"completed":@(r.completed),@"written":@(r.written),@"errors":@(r.errors),@"guard_errors":@(r.guardErrors)};}
