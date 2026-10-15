#import <Metal/Metal.h>
#include "KeplerCompat.h"
#include <cstdio>
#include <cstring>
#include <string>
struct KCContext {
 id<MTLDevice> device;
 id<MTLCommandQueue> queue;
 id<MTLComputePipelineState> pipeline;
 id<MTLBuffer> input,output,private_input,private_output;
 uint32_t rows,columns;
 std::string name;
};
KCContext* kc_create(uint32_t rows,uint32_t columns){@autoreleasepool{
 if(!rows||!columns)return nullptr;auto*c=new KCContext();
 for(id<MTLDevice>d in MTLCopyAllDevices())if([d.name containsString:@"880M"])c->device=d;
 if(!c->device){delete c;return nullptr;}c->name=c->device.name.UTF8String;c->rows=rows;c->columns=columns;
 // Real GPU reductions using threadgroup memory; no unsupported SIMD intrinsics.
 NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void softmax_legacy(device const float*x [[buffer(0)]],device float*y [[buffer(1)]],constant uint2&dims [[buffer(2)]],uint row [[threadgroup_position_in_grid]],uint tid [[thread_index_in_threadgroup]]){\n"
 "threadgroup float s[128];uint cols=dims.y;float mx=-INFINITY;for(uint j=tid;j<cols;j+=128)mx=max(mx,x[row*cols+j]);s[tid]=mx;threadgroup_barrier(mem_flags::mem_threadgroup);\n"
 "for(uint stride=64;stride>0;stride/=2){if(tid<stride)s[tid]=max(s[tid],s[tid+stride]);threadgroup_barrier(mem_flags::mem_threadgroup);}mx=s[0];threadgroup_barrier(mem_flags::mem_threadgroup);\n"
 "float sum=0;for(uint j=tid;j<cols;j+=128){float e=exp(x[row*cols+j]-mx);y[row*cols+j]=e;sum+=e;}s[tid]=sum;threadgroup_barrier(mem_flags::mem_threadgroup);\n"
 "for(uint stride=64;stride>0;stride/=2){if(tid<stride)s[tid]+=s[tid+stride];threadgroup_barrier(mem_flags::mem_threadgroup);}float total=s[0];for(uint j=tid;j<cols;j+=128)y[row*cols+j]/=total;}";
 MTLCompileOptions*options=[MTLCompileOptions new];options.languageVersion=MTLLanguageVersion1_2;options.fastMathEnabled=NO;NSError*error=nil;
 id<MTLLibrary>library=[c->device newLibraryWithSource:src options:options error:&error];if(!library){fprintf(stderr,"kc library: %s\n",error.description.UTF8String);delete c;return nullptr;}
 c->pipeline=[c->device newComputePipelineStateWithFunction:[library newFunctionWithName:@"softmax_legacy"] error:&error];if(!c->pipeline){fprintf(stderr,"kc pipeline: %s\n",error.description.UTF8String);delete c;return nullptr;}
 size_t bytes=size_t(rows)*columns*sizeof(float);c->input=[c->device newBufferWithLength:bytes options:MTLResourceStorageModeShared];c->output=[c->device newBufferWithLength:bytes options:MTLResourceStorageModeShared];c->private_input=[c->device newBufferWithLength:bytes options:MTLResourceStorageModePrivate];c->private_output=[c->device newBufferWithLength:bytes options:MTLResourceStorageModePrivate];c->queue=[c->device newCommandQueue];if(!c->input||!c->output||!c->private_input||!c->private_output||!c->queue){delete c;return nullptr;}return c;
}}
const char*kc_device_name(KCContext*c){return c?c->name.c_str():"";}
int kc_softmax(KCContext*c,const float*input,float*output,double*gpu_seconds){@autoreleasepool{
 if(!c||!input||!output)return 1;size_t bytes=size_t(c->rows)*c->columns*sizeof(float);memcpy(c->input.contents,input,bytes);
 id<MTLCommandBuffer>command=[c->queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:c->pipeline];[encoder setBuffer:c->input offset:0 atIndex:0];[encoder setBuffer:c->output offset:0 atIndex:1];uint32_t dims[2]={c->rows,c->columns};[encoder setBytes:dims length:sizeof(dims) atIndex:2];[encoder dispatchThreadgroups:MTLSizeMake(c->rows,1,1) threadsPerThreadgroup:MTLSizeMake(128,1,1)];[encoder endEncoding];[command commit];[command waitUntilCompleted];if(command.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"kc command: %s\n",command.error.description.UTF8String);return 2;}memcpy(output,c->output.contents,bytes);if(gpu_seconds)*gpu_seconds=command.GPUEndTime-command.GPUStartTime;return 0;
}}
void kc_destroy(KCContext*c){delete c;}
int kc_upload(KCContext*c,const float*input){@autoreleasepool{
 if(!c||!input)return 1;size_t bytes=size_t(c->rows)*c->columns*sizeof(float);memcpy(c->input.contents,input,bytes);id<MTLCommandBuffer>cmd=[c->queue commandBuffer];id<MTLBlitCommandEncoder>enc=[cmd blitCommandEncoder];[enc copyFromBuffer:c->input sourceOffset:0 toBuffer:c->private_input destinationOffset:0 size:bytes];[enc endEncoding];[cmd commit];[cmd waitUntilCompleted];return cmd.status==MTLCommandBufferStatusCompleted?0:2;
}}
int kc_run_resident(KCContext*c,double*gpu_seconds){@autoreleasepool{
 if(!c)return 1;id<MTLCommandBuffer>cmd=[c->queue commandBuffer];id<MTLComputeCommandEncoder>enc=[cmd computeCommandEncoder];[enc setComputePipelineState:c->pipeline];[enc setBuffer:c->private_input offset:0 atIndex:0];[enc setBuffer:c->private_output offset:0 atIndex:1];uint32_t dims[2]={c->rows,c->columns};[enc setBytes:dims length:sizeof(dims) atIndex:2];[enc dispatchThreadgroups:MTLSizeMake(c->rows,1,1) threadsPerThreadgroup:MTLSizeMake(128,1,1)];[enc endEncoding];[cmd commit];[cmd waitUntilCompleted];if(cmd.status!=MTLCommandBufferStatusCompleted)return 2;if(gpu_seconds)*gpu_seconds=cmd.GPUEndTime-cmd.GPUStartTime;return 0;
}}
int kc_download(KCContext*c,float*output){@autoreleasepool{
 if(!c||!output)return 1;size_t bytes=size_t(c->rows)*c->columns*sizeof(float);id<MTLCommandBuffer>cmd=[c->queue commandBuffer];id<MTLBlitCommandEncoder>enc=[cmd blitCommandEncoder];[enc copyFromBuffer:c->private_output sourceOffset:0 toBuffer:c->output destinationOffset:0 size:bytes];[enc endEncoding];[cmd commit];[cmd waitUntilCompleted];if(cmd.status!=MTLCommandBufferStatusCompleted)return 2;memcpy(output,c->output.contents,bytes);return 0;
}}
