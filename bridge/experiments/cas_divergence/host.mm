// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstring>

struct Params { uint32_t seed, local, pattern, variant; };

int main(int argc,char**argv) { @autoreleasepool {
 if(argc!=4)return 2;
 NSString *libraryPath=@(argv[1]),*output=@(argv[2]),*deviceNeedle=@(argv[3]);
 id<MTLDevice> selected=nil;
 for(id<MTLDevice> device in MTLCopyAllDevices()) if([device.name containsString:deviceNeedle]) {
  if(selected){fprintf(stderr,"Ambiguous device selection\n");return 3;}selected=device;
 }
 if(!selected){fprintf(stderr,"Requested device not found\n");return 3;}
 NSError *error=nil;id<MTLLibrary> library=[selected newLibraryWithURL:[NSURL fileURLWithPath:libraryPath] error:&error];
 id<MTLFunction> function=[library newFunctionWithName:@"divergence_case"];
 id<MTLComputePipelineState> pipeline=function?[selected newComputePipelineStateWithFunction:function error:&error]:nil;
 if(!pipeline){fprintf(stderr,"Pipeline: %s\n",error.description.UTF8String?:"nil");return 4;}
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
   NSData *data=[NSData dataWithBytes:stage.contents length:bytes];
   if(![data writeToFile:[output stringByAppendingPathComponent:file] atomically:YES])return 9;
   [records addObject:@{@"local":@(local),@"groups":@3,@"pattern":@(pattern),@"variant":@(variant),
       @"repeat":@(repeat),@"seed":@(p.seed),@"file":file,@"status":@(cmd.status)}];
   [stage release];[target release];
  }}
 NSDictionary *report=@{@"device":selected.name,@"registry_id":@(selected.registryID),
   @"pipeline_max_threads":@(pipeline.maxTotalThreadsPerThreadgroup),
   @"threadgroup_memory_bytes":@(pipeline.staticThreadgroupMemoryLength),@"runs":records};
 NSData *json=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:&error];
 if(!json)return 10;fwrite(json.bytes,1,json.length,stdout);puts("");
 [queue release];[pipeline release];[function release];[library release];return 0;
}}
