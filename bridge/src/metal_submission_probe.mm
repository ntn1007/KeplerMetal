#import <Metal/Metal.h>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
void mark(const char*s){auto fn=(void(*)(const char*))dlsym(RTLD_DEFAULT,"kepler_trace_mark");if(fn)fn(s);}
int main(){@autoreleasepool{
 mark("create_device");id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d||![d.name containsString:@"880M"])return 1;
 mark("compile_pipeline");NSError*error=nil;MTLCompileOptions*o=[MTLCompileOptions new];o.languageVersion=MTLLanguageVersion1_2;o.fastMathEnabled=NO;
 NSString*src=@"#include <metal_stdlib>\nusing namespace metal;kernel void affine(device const float*x [[buffer(0)]],device float*y [[buffer(1)]],uint i [[thread_position_in_grid]]){y[i]=x[i]*3.0f+2.0f;}";
 id<MTLLibrary>library=[d newLibraryWithSource:src options:o error:&error];if(!library){fprintf(stderr,"%s\n",error.description.UTF8String);return 2;}
 id<MTLComputePipelineState>pipeline=[d newComputePipelineStateWithFunction:[library newFunctionWithName:@"affine"] error:&error];if(!pipeline)return 3;
 const size_t n=1024,bytes=n*sizeof(float);mark("allocate_resources");id<MTLBuffer>staging_in=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];id<MTLBuffer>staging_out=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];id<MTLBuffer>input=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate];id<MTLBuffer>output=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate];if(!staging_in||!staging_out||!input||!output)return 4;
 for(size_t i=0;i<n;i++)((float*)staging_in.contents)[i]=float(i%128);
 mark("create_queue");id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cmd=[q commandBuffer];
 mark("encode");id<MTLBlitCommandEncoder>blit=[cmd blitCommandEncoder];[blit copyFromBuffer:staging_in sourceOffset:0 toBuffer:input destinationOffset:0 size:bytes];[blit endEncoding];id<MTLComputeCommandEncoder>enc=[cmd computeCommandEncoder];[enc setComputePipelineState:pipeline];[enc setBuffer:input offset:0 atIndex:0];[enc setBuffer:output offset:0 atIndex:1];[enc dispatchThreadgroups:MTLSizeMake(n/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[enc endEncoding];blit=[cmd blitCommandEncoder];[blit copyFromBuffer:output sourceOffset:0 toBuffer:staging_out destinationOffset:0 size:bytes];[blit endEncoding];
 mark("submit");[cmd commit];[cmd waitUntilCompleted];mark("validate");if(cmd.status!=MTLCommandBufferStatusCompleted)return 5;
 size_t bad=0;for(size_t i=0;i<n;i++)if(((float*)staging_out.contents)[i]!=float(i%128)*3+2)bad++;
 printf("{\"device\":\"%s\",\"registry_id\":%llu,\"elements\":%zu,\"mismatches\":%zu,\"gpu_seconds\":%.9f,\"command_status\":%ld,\"scope\":\"existing Metal driver observed in this process\"}\n",d.name.UTF8String,(unsigned long long)d.registryID,n,bad,cmd.GPUEndTime-cmd.GPUStartTime,(long)cmd.status);mark("finished");return bad?6:0;
}}
