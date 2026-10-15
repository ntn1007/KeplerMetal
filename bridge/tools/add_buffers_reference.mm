// Reference execution through the installed Metal driver, not through NAK.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <cstdio>
#include <vector>
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=2)return 1;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();
 if(!device||![device.name containsString:@"880M"])return 2;
 NSError*error=nil;
 id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]]] error:&error];
 if(!library){fprintf(stderr,"library: %s\n",error.description.UTF8String);return 3;}
 id<MTLComputePipelineState>pipeline=[device newComputePipelineStateWithFunction:[library newFunctionWithName:@"add_buffers"] error:&error];
 if(!pipeline){fprintf(stderr,"pipeline: %s\n",error.description.UTF8String);return 4;}
 const uint32_t count=1041,total=1088;const float canary=-123456.f;
 std::vector<float>a(total),b(total),output(total,canary);
 for(uint32_t i=0;i<total;i++){a[i]=float(int(i%127)-63)*.25f;b[i]=float(int(i%31)-15)*.5f;}
 id<MTLBuffer>ba=[device newBufferWithBytes:a.data() length:total*sizeof(float) options:MTLResourceStorageModeShared];
 id<MTLBuffer>bb=[device newBufferWithBytes:b.data() length:total*sizeof(float) options:MTLResourceStorageModeShared];
 id<MTLBuffer>bo=[device newBufferWithBytes:output.data() length:total*sizeof(float) options:MTLResourceStorageModeShared];
 id<MTLBuffer>bn=[device newBufferWithBytes:&count length:sizeof(count) options:MTLResourceStorageModeShared];
 if(!ba||!bb||!bo||!bn)return 5;
 id<MTLCommandQueue>queue=[device newCommandQueue];id<MTLCommandBuffer>command=[queue commandBuffer];
 id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:pipeline];
 [encoder setBuffer:ba offset:0 atIndex:0];[encoder setBuffer:bb offset:0 atIndex:1];
 [encoder setBuffer:bo offset:0 atIndex:2];[encoder setBuffer:bn offset:0 atIndex:3];
 [encoder dispatchThreadgroups:MTLSizeMake(total/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
 [encoder endEncoding];[command commit];[command waitUntilCompleted];
 if(command.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"command: %s\n",command.error.description.UTF8String);return 6;}
 const float*values=(const float*)bo.contents;uint32_t bad=0,bad_guard=0;
 for(uint32_t i=0;i<count;i++)if(values[i]!=a[i]+b[i])bad++;
 for(uint32_t i=count;i<total;i++)if(values[i]!=canary)bad_guard++;
 printf("{\"device\":\"%s\",\"active_elements\":%u,\"guard_elements\":%u,\"mismatches\":%u,\"changed_guard_elements\":%u,\"gpu_seconds\":%.9f,\"requested_buffer_bytes\":%zu,\"scope\":\"same precompiled Metal source executed by installed driver; not NAK binary\"}\n",device.name.UTF8String,count,total-count,bad,bad_guard,command.GPUEndTime-command.GPUStartTime,size_t(total)*sizeof(float)*3+sizeof(count));
 return bad||bad_guard?7:0;
}}
