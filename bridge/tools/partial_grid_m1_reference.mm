// SPDX-License-Identifier: MIT
// Tiny native Apple Metal reference for nonuniform builtins; no Kepler code.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <unistd.h>
#include <cstring>

static NSString *kernelSource=@"#include <metal_stdlib>\n"
 "using namespace metal;\n"
 "kernel void observe(device uint4 *out [[buffer(0)]], device atomic_uint *counter [[buffer(1)]], "
 "threadgroup uint *scratch [[threadgroup(0)]], uint3 gid [[thread_position_in_grid]], "
 "uint3 lane [[thread_position_in_threadgroup]], uint3 group [[threadgroup_position_in_grid]], "
 "uint3 groups [[threadgroups_per_grid]], uint3 local [[threads_per_threadgroup]], "
 "uint3 dispatchLocal [[dispatch_threads_per_threadgroup]], uint3 grid [[threads_per_grid]], "
 "uint index [[thread_index_in_threadgroup]]) { "
 "if(index==0) scratch[0]=local.x*local.y*local.z; threadgroup_barrier(mem_flags::mem_threadgroup); "
 "uint i=gid.x+grid.x*(gid.y+grid.y*gid.z); uint b=i*8; "
 "out[b]=uint4(gid, i); out[b+1]=uint4(lane, index); out[b+2]=uint4(group,0); "
 "out[b+3]=uint4(groups,0); out[b+4]=uint4(local,0); out[b+5]=uint4(dispatchLocal,0); "
 "out[b+6]=uint4(grid,0); out[b+7]=uint4(scratch[0],0,0,0); "
 "atomic_fetch_add_explicit(counter,1u,memory_order_relaxed); }";
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=3||(strcmp(argv[1],"partial3d")&&strcmp(argv[1],"partial1d")&&strcmp(argv[1],"negative3d")))return 1;
 if(!getuid()||getuid()!=geteuid())return 2;
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d||![d supportsFamily:MTLGPUFamilyApple4])return 3;
 NSError*error=nil;MTLCompileOptions*options=[MTLCompileOptions new];options.languageVersion=MTLLanguageVersion2_3;
 id<MTLLibrary>lib=[d newLibraryWithSource:kernelSource options:options error:&error];if(!lib){fprintf(stderr,"compile: %s\n",error.description.UTF8String?:"");return 4;}
 id<MTLComputePipelineState>pipe=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"observe"] error:&error];if(!pipe){fprintf(stderr,"pipeline: %s\n",error.description.UTF8String?:"");return 5;}
 bool one=!strcmp(argv[1],"partial1d"),negative=!strcmp(argv[1],"negative3d");MTLSize grid=one?MTLSizeMake(33,1,1):MTLSizeMake(11,7,5),local=one?MTLSizeMake(32,1,1):MTLSizeMake(4,4,3);
 NSUInteger n=grid.width*grid.height*grid.depth,bytes=n*8*16,guard=64;
 id<MTLBuffer>out=[d newBufferWithLength:bytes+2*guard options:MTLResourceStorageModeShared],counter=[d newBufferWithLength:4 options:MTLResourceStorageModeShared];
 if(!out||!counter||!out.contents||!counter.contents)return 6;memset(out.contents,0xa5,out.length);*(uint32_t*)counter.contents=0;
 NSUInteger status=0;if(!negative){id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];if(!q||!cb||!e)return 7;
 [e setComputePipelineState:pipe];[e setBuffer:out offset:guard atIndex:0];[e setBuffer:counter offset:0 atIndex:1];[e setThreadgroupMemoryLength:16 atIndex:0];
 [e dispatchThreads:grid threadsPerThreadgroup:local];[e endEncoding];[cb commit];[cb waitUntilCompleted];status=cb.status;if(status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"command: %s\n",cb.error.description.UTF8String?:"");return 8;}}
 NSString*dest=@(argv[2]);if(![[NSData dataWithBytes:out.contents length:out.length]writeToFile:[dest stringByAppendingPathComponent:@"output.bin"] options:0 error:&error])return 9;
 NSDictionary*r=@{@"mode":@(argv[1]),@"device":d.name?:@"",@"registry_id":@(d.registryID),@"pid":@(getpid()),@"uid":@(getuid()),@"euid":@(geteuid()),@"grid":@[@(grid.width),@(grid.height),@(grid.depth)],@"dispatch_local":@[@(local.width),@(local.height),@(local.depth)],@"elements":@(n),@"guard":@(guard),@"output_bytes":@(out.length),@"counter":@(*(uint32_t*)counter.contents),@"command_status":@(status),@"submitted":@(!negative),@"threadgroup_barrier_used":@YES,@"supports_apple4":@YES};
 NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];if(!j)return 10;fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
