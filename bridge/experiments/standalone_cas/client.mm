// SPDX-License-Identifier: MIT
// Purpose-built public Metal client: no KeplerMetal headers or symbols.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstring>
struct Params {uint32_t seed,n,local,groups,variant;};
static_assert(sizeof(Params)==20,"parameter ABI");
int main(int argc,char **argv){@autoreleasepool{@try{
 if(argc!=4)return 1;NSString *libraryPath=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
 if(![mode isEqual:@"run"]&&![mode isEqual:@"construct"])return 1;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device){fprintf(stderr,"no device\n");return 3;}
 if(![device.name isEqual:@"NVIDIA GeForce GTX 880M"])return 2;
 NSError *error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:libraryPath] error:&error];
 if(!library){fprintf(stderr,"library failed\n");return 4;}
 NSArray *names=@[@"sdk_cas_expected",@"sdk_cas_slot",@"sdk_cas_noise",@"sdk_cas_swizzle",@"sdk_keep_comparand"];
 NSMutableArray *pipelines=[NSMutableArray new],*proofs=[NSMutableArray new],*runs=[NSMutableArray new];
 for(NSString*name in names){id<MTLFunction>f=[library newFunctionWithName:name];id<MTLComputePipelineState>p=f?[device newComputePipelineStateWithFunction:f error:&error]:nil;
  if(!p){fprintf(stderr,"pipeline failed %s\n",name.UTF8String);return 5;}
  [pipelines addObject:p];[proofs addObject:@{@"function":name,@"pipeline_max_threads":@(p.maxTotalThreadsPerThreadgroup)}];}
 if([mode isEqual:@"run"]){id<MTLCommandQueue>queue=[device newCommandQueue];if(!queue)return 6;
  for(NSUInteger k=0;k<names.count;k++)for(NSNumber*localValue in @[@33,@128,@1024])for(NSUInteger variant=0;variant<2;variant++)for(NSUInteger iteration=0;iteration<3;iteration++){@autoreleasepool{
   uint32_t local=localValue.unsignedIntValue;Params params={0x2468u+53u*(uint32_t)iteration,local*3,local,3,(uint32_t)variant};id<MTLComputePipelineState>p=pipelines[k];if(p.maxTotalThreadsPerThreadgroup<local)return 7;
   NSUInteger bytes=params.n*16+128;id<MTLBuffer>staging=[device newBufferWithLength:bytes options:MTLResourceStorageModeShared],output=[device newBufferWithLength:bytes options:MTLResourceStorageModePrivate],unused=[device newBufferWithLength:params.n*4 options:MTLResourceStorageModePrivate];if(!staging||!output||!unused)return 8;memset(staging.contents,0xa5,bytes);
   id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromBuffer:staging sourceOffset:0 toBuffer:output destinationOffset:0 size:bytes];[b endEncoding];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:p];[e setBytes:&params length:sizeof params atIndex:0];[e setBuffer:output offset:64 atIndex:1];[e setBuffer:unused offset:0 atIndex:3];[e dispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[e endEncoding];b=[cb blitCommandEncoder];[b copyFromBuffer:output sourceOffset:0 toBuffer:staging destinationOffset:0 size:bytes];[b endEncoding];[cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted)return 9;
   NSString*file=[NSString stringWithFormat:@"%@-l%u-v%lu-i%lu.bin",names[k],local,(unsigned long)variant,(unsigned long)iteration];if(![[NSData dataWithBytes:staging.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:file] atomically:YES])return 10;
   [runs addObject:@{@"function":names[k],@"candidate":@(k!=4),@"layout":k==2?@"noise":k==3?@"permuted":@"standard",@"local":@(local),@"groups":@3,@"variant":@(variant),@"iteration":@(iteration),@"seed":@(params.seed),@"file":file,@"committed":@YES,@"command_status":@(cb.status)}];
  }}
 }
 NSDictionary*result=@{@"client_mode":mode,@"device":device.name,@"registry_id":@(device.registryID),@"proofs":proofs,@"runs":runs,@"system_modified":@NO};NSData*data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];if(!data)return 11;fwrite(data.bytes,1,data.length,stdout);puts("");return 0;
 }@catch(NSException*e){fprintf(stderr,"exception %s\n",e.name.UTF8String);return 12;}}}
