// SPDX-License-Identifier: MIT
// Process-local indirect-branch witness; owned output only.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#include <cstring>
#include <cstdlib>
extern "C" id<MTLComputePipelineState> KPConditionalCB0WitnessPipeline(
 id<MTLDevice>,NSData*,NSData*,NSData*,NSData*,NSError**,NSDictionary**);
static void emit(NSDictionary*d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];if(j)fwrite(j.bytes,1,j.length,stdout);puts("");fflush(stdout);}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=8)return 1;NSString*out=@(argv[1]),*mode=@(argv[2]);char*end=nullptr;long pattern=strtol(argv[7],&end,10);
 if(![@[@"baseline",@"trace"] containsObject:mode]||!end||*end||pattern<0||pattern>4)return 1;
 NSData*library=[NSData dataWithContentsOfFile:@(argv[3])],*metadata=[NSData dataWithContentsOfFile:@(argv[4])];
 NSData*original=[NSData dataWithContentsOfFile:@(argv[5])],*replacement=[NSData dataWithContentsOfFile:@(argv[6])];
 if(!library||!metadata||!original||!replacement)return 2;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(KPKepler880MIdentity(x)){if(d)return 3;d=x;}if(!d)return 3;
 NSError*error=nil;NSDictionary*proof=nil;
 id<MTLComputePipelineState>p=KPConditionalCB0WitnessPipeline(d,library,metadata,original,replacement,&error,&proof);
 if(!p){emit(@{@"status":@"PIPELINE_REFUSED",@"GPU_dispatch":@NO,@"error":error.description?:@"",@"import":proof?:@{}});return 4;}
 if(p.maxTotalThreadsPerThreadgroup<33){[p release];return 5;}
 id<MTLCommandQueue>q=[d newCommandQueue];const NSUInteger n=99,bytes=128+n*16;
 NSMutableData*initial=[NSMutableData dataWithLength:bytes];memset(initial.mutableBytes,0xa5,bytes);
 id<MTLBuffer>stage=[d newBufferWithBytes:initial.bytes length:bytes options:MTLResourceStorageModeShared];
 id<MTLBuffer>target=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate];if(!q||!stage||!target)return 6;
 struct {uint32_t seed,local,pattern,variant;}params={0x1234,33,(uint32_t)pattern,1};
 id<MTLCommandBuffer>cmd=[q commandBuffer];id<MTLBlitCommandEncoder>blit=[cmd blitCommandEncoder];
 [blit copyFromBuffer:stage sourceOffset:0 toBuffer:target destinationOffset:0 size:bytes];[blit endEncoding];
 id<MTLComputeCommandEncoder>compute=[cmd computeCommandEncoder];[compute setComputePipelineState:p];
 [compute setBytes:&params length:sizeof(params) atIndex:0];[compute setBuffer:target offset:64 atIndex:1];
 [compute dispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake(33,1,1)];[compute endEncoding];
 blit=[cmd blitCommandEncoder];[blit copyFromBuffer:target sourceOffset:0 toBuffer:stage destinationOffset:0 size:bytes];[blit endEncoding];
 [cmd commit];[cmd waitUntilCompleted];if(cmd.status!=MTLCommandBufferStatusCompleted)return 7;
 if(![[NSData dataWithBytes:stage.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:@"output.bin"] atomically:YES])return 8;
 emit(@{@"status":@"COMPLETED",@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),
        @"GPU_dispatch":@YES,@"command_status":@(cmd.status),@"threads":@33,@"groups":@3,
        @"pattern":@(pattern),@"variant":@1,@"seed":@0x1234,@"import":proof?:@{}});
 [stage release];[target release];[q release];[p release];return 0;
}}
