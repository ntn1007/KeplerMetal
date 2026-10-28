// SPDX-License-Identifier: MIT
// Explicit laboratory client using a byte-pinned NVIDIA program import.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#include <cstring>

extern "C" id<MTLComputePipelineState> KPInternalCASCreatePreservingNativeCASPipeline(
 id<MTLDevice>,NSURL*,NSString*,NSData*,NSData*,NSError**,NSDictionary**);

struct Params { uint32_t seed, local, pattern, variant; };
static void emit(NSDictionary *value) {
 NSData *json=[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];
 if(json)fwrite(json.bytes,1,json.length,stdout);puts("");fflush(stdout);
}

int main(int argc,char**argv) { @autoreleasepool {
 if(argc!=6)return 2;
 NSString *libraryPath=@(argv[1]),*output=@(argv[2]),*mode=@(argv[3]);
 if(![@[@"native",@"replay",@"trampoline",@"repaired",@"negative-pin"] containsObject:mode])return 2;
 id<MTLDevice> selected=nil;
 for(id<MTLDevice> device in MTLCopyAllDevices()) if(KPKepler880MIdentity(device)) {
  if(selected){fprintf(stderr,"Ambiguous GPU\n");return 3;}selected=device;
 }
 if(!selected)return 3;
 NSError *error=nil;NSDictionary *proof=nil;id<MTLComputePipelineState> pipeline=nil;
 if([mode isEqual:@"native"]) {
  id<MTLLibrary> library=[selected newLibraryWithURL:[NSURL fileURLWithPath:libraryPath] error:&error];
  id<MTLFunction> function=[library newFunctionWithName:@"divergence_case"];
  if(function)pipeline=[selected newComputePipelineStateWithFunction:function error:&error];
  [function release];[library release];
 } else {
  NSData *original=[NSData dataWithContentsOfFile:@(argv[4])],*replacement=[NSData dataWithContentsOfFile:@(argv[5])];
  pipeline=KPInternalCASCreatePreservingNativeCASPipeline(selected,[NSURL fileURLWithPath:libraryPath],
              @"divergence_case",original,replacement,&error,&proof);
 }
 if(!pipeline) {
  emit(@{@"mode":mode,@"failure_stage":@"pipeline",@"GPU_dispatch":@NO,@"error":error.description?:@"nil",@"import":proof?:@{}});
  return 4;
 }
 if([mode isEqual:@"negative-pin"]){[pipeline release];return 11;}
 id<MTLCommandQueue> queue=[selected newCommandQueue];if(!queue)return 5;
 NSMutableArray *records=[NSMutableArray array];
 for(NSNumber*number in @[@33,@128,@1024])for(uint pattern=0;pattern<4;pattern++)
  for(uint variant=0;variant<2;variant++)for(uint repeat=0;repeat<2;repeat++) { @autoreleasepool {
   uint local=number.unsignedIntValue;if(local>pipeline.maxTotalThreadsPerThreadgroup)return 6;
   Params p={0x1234u+37u*repeat,local,pattern,variant};NSUInteger n=local*3,bytes=n*16+128;
   NSMutableData *initial=[NSMutableData dataWithLength:bytes];memset(initial.mutableBytes,0xa5,bytes);
   id<MTLBuffer> stage=[selected newBufferWithBytes:initial.bytes length:bytes options:MTLResourceStorageModeShared];
   id<MTLBuffer> target=[selected newBufferWithLength:bytes options:MTLResourceStorageModePrivate];
   if(!stage||!target)return 7;
   id<MTLCommandBuffer> cmd=[queue commandBuffer];
   id<MTLBlitCommandEncoder> blit=[cmd blitCommandEncoder];
   [blit copyFromBuffer:stage sourceOffset:0 toBuffer:target destinationOffset:0 size:bytes];[blit endEncoding];
   id<MTLComputeCommandEncoder> compute=[cmd computeCommandEncoder];
   [compute setComputePipelineState:pipeline];[compute setBytes:&p length:sizeof(p) atIndex:0];
   [compute setBuffer:target offset:64 atIndex:1];
   [compute dispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[compute endEncoding];
   blit=[cmd blitCommandEncoder];[blit copyFromBuffer:target sourceOffset:0 toBuffer:stage destinationOffset:0 size:bytes];[blit endEncoding];
   [cmd commit];[cmd waitUntilCompleted];
   if(cmd.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"GPU execution failed: %s\n",cmd.error.description.UTF8String?:"nil");return 8;}
   NSString *file=[NSString stringWithFormat:@"l%u-p%u-v%u-r%u.bin",local,pattern,variant,repeat];
   if(![[NSData dataWithBytes:stage.contents length:bytes]writeToFile:[output stringByAppendingPathComponent:file] atomically:YES])return 9;
   [records addObject:@{@"local":@(local),@"groups":@3,@"pattern":@(pattern),@"variant":@(variant),
       @"repeat":@(repeat),@"seed":@(p.seed),@"file":file,@"status":@(cmd.status)}];
   [stage release];[target release];
  }}
 emit(@{@"mode":mode,@"device":selected.name,@"registry_id":@(selected.registryID),@"GPU_dispatch":@YES,
   @"pipeline_max_threads":@(pipeline.maxTotalThreadsPerThreadgroup),
   @"threadgroup_memory_bytes":@(pipeline.staticThreadgroupMemoryLength),@"import":proof?:@{},@"runs":records});
 [queue release];[pipeline release];return 0;
}}
