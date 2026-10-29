// SPDX-License-Identifier: MIT
// Native Apple Metal state reference; no KeplerMetal injection or driver change.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
static void need(BOOL ok, NSString *message){if(!ok){fprintf(stderr,"FAIL: %s\n",message.UTF8String);exit(1);}}
static void save(NSString *dir,NSString *name,id<MTLBuffer> b){
 NSString *path=[dir stringByAppendingPathComponent:name];int fd=open(path.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);need(fd>=0,@"output open");
 const unsigned char*p=(const unsigned char*)b.contents;NSUInteger pos=0;while(pos<b.length){ssize_t n=write(fd,p+pos,b.length-pos);need(n>0,@"output write");pos+=(NSUInteger)n;}need(close(fd)==0,@"output close");
}
int main(int argc,const char**argv){@autoreleasepool{
 need(argc==2,@"fresh capture directory required");NSString*out=[NSString stringWithUTF8String:argv[1]];need(out!=nil,@"invalid output directory");
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();need(d!=nil,@"device");id<MTLCommandQueue>q=[d newCommandQueue];need(q!=nil,@"queue");
 NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
  "kernel void a(device uint* out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = 0x1000u + i; }\n"
  "kernel void b(device uint* out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = 0x2000u + i; }\n";
 NSError*err=nil;id<MTLLibrary>lib=[d newLibraryWithSource:src options:nil error:&err];need(lib!=nil,err.localizedDescription?:@"library");
 NSMutableArray<id<MTLComputePipelineState>>*states=[NSMutableArray new];
 for(NSString*n in @[@"a",@"b"]){MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=[lib newFunctionWithName:n];p.supportIndirectCommandBuffers=YES;id<MTLComputePipelineState>s=[d newComputePipelineStateWithDescriptor:p options:0 reflection:nil error:&err];need(s!=nil,err.localizedDescription?:@"pipeline");[states addObject:s];}
 MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.inheritPipelineState=YES;desc.inheritBuffers=NO;desc.maxKernelBufferBindCount=1;
 id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:2 options:MTLResourceStorageModeShared];need(icb!=nil,@"ICB");
 NSMutableArray<id<MTLBuffer>>*buffers=[NSMutableArray new];for(int i=0;i<5;i++){id<MTLBuffer>b=[d newBufferWithLength:256 options:MTLResourceStorageModeShared];need(b&&b.contents,@"buffer");memset(b.contents,0xa5,b.length);[buffers addObject:b];}
 for(NSUInteger i=0;i<2;i++){id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:i];need(c!=nil,@"ICB command");[c setKernelBuffer:buffers[i*2] offset:0 atIndex:0];[c concurrentDispatchThreadgroups:MTLSizeMake(2,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];}
 id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];need(cb&&e,@"encoder");
 for(NSUInteger i=0;i<2;i++){
  [e setComputePipelineState:states[i]];[e setBuffer:buffers[i*2+1] offset:0 atIndex:0];
  [e useResource:buffers[i*2] usage:MTLResourceUsageWrite];[e executeCommandsInBuffer:icb withRange:NSMakeRange(i,1)];
  // No parent pipeline or buffer setter between ICB execution and direct dispatch.
  [e dispatchThreadgroups:MTLSizeMake(2,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
 }
 [e endEncoding];[cb commit];[cb waitUntilCompleted];need(cb.status==MTLCommandBufferStatusCompleted,cb.error.localizedDescription?:@"completion");
 for(NSUInteger i=0;i<4;i++){uint32_t base=i<2?0x1000:0x2000;const uint32_t*p=(const uint32_t*)buffers[i].contents;for(uint32_t j=0;j<64;j++)need(p[j]==base+j,@"parent or ICB state mismatch");save(out,[NSString stringWithFormat:@"%@-%lu.bin",i%2?@"parent":@"icb",(unsigned long)(i/2)],buffers[i]);}
 const uint32_t*blank=(const uint32_t*)buffers[4].contents;for(int i=0;i<64;i++)need(blank[i]==0xa5a5a5a5u,@"untouched control changed");save(out,@"untouched.bin",buffers[4]);
 NSDictionary*result=@{@"status":@"PASS_NATIVE_STATE_REFERENCE",@"device":d.name,@"registry_id":@(d.registryID),@"pipeline_order":@[@"a",@"b"],@"indirect_runs":@2,@"direct_after_icb_runs":@2,@"words_checked":@256,@"control_words":@64,@"single_encoder":@YES,@"parent_rebound_after_icb":@NO,@"kepler_gpu_tested":@NO};
 NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&err];need(json!=nil,err.localizedDescription?:@"json");fwrite(json.bytes,1,json.length,stdout);putchar('\n');return 0;
}}
