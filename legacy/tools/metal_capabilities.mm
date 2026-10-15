#import <Metal/Metal.h>
#include <cstdio>
#include <cmath>
#include <initializer_list>
NSDictionary* execute(id<MTLDevice>d,NSString*src,int language){
 NSMutableDictionary*r=[@{@"language_raw":@(language)} mutableCopy];NSError*err=nil;MTLCompileOptions*o=[MTLCompileOptions new];o.languageVersion=(MTLLanguageVersion)language;o.fastMathEnabled=NO;
 id<MTLLibrary>lib=[d newLibraryWithSource:src options:o error:&err];r[@"library_ok"]=@(lib!=nil);if(!lib){r[@"error"]=err.description?:@"unknown";return r;}
 id<MTLComputePipelineState>pipeline=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"test"] error:&err];r[@"pipeline_ok"]=@(pipeline!=nil);if(!pipeline){r[@"error"]=err.description?:@"unknown";return r;}
 const size_t n=1024;id<MTLBuffer>in=[d newBufferWithLength:n*4 options:MTLResourceStorageModeShared];id<MTLBuffer>out=[d newBufferWithLength:n*4 options:MTLResourceStorageModeShared];float*x=(float*)in.contents;for(size_t i=0;i<n;i++)x[i]=float(i%512);
 id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cmd=[q commandBuffer];id<MTLComputeCommandEncoder>enc=[cmd computeCommandEncoder];[enc setComputePipelineState:pipeline];[enc setBuffer:in offset:0 atIndex:0];[enc setBuffer:out offset:0 atIndex:1];[enc dispatchThreadgroups:MTLSizeMake(n/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[enc endEncoding];[cmd commit];[cmd waitUntilCompleted];r[@"command_status"]=@(cmd.status);r[@"gpu_seconds"]=@(cmd.GPUEndTime-cmd.GPUStartTime);if(cmd.error)r[@"error"]=cmd.error.description;
 size_t bad=0;float*y=(float*)out.contents;for(size_t i=0;i<n;i++)if(y[i]!=2*x[i]+1)bad++;r[@"mismatches"]=@(bad);r[@"execution_ok"]=@(cmd.status==MTLCommandBufferStatusCompleted&&bad==0);return r;
}
int main(){@autoreleasepool{
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d)return 1;NSMutableDictionary*r=[@{@"device":d.name,@"registry_id":@(d.registryID),@"unified_memory":@(d.hasUnifiedMemory),@"recommended_bytes":@(d.recommendedMaxWorkingSetSize),@"argument_buffers_tier":@(d.argumentBuffersSupport),@"max_threadgroup_memory_bytes":@(d.maxThreadgroupMemoryLength)} mutableCopy];
 NSMutableDictionary*f=[NSMutableDictionary new];for(int code:{2001,2002,3001,3002,3003,5001,5002})f[[NSString stringWithFormat:@"%d",code]]=@([d supportsFamily:(MTLGPUFamily)code]);r[@"gpu_families"]=f;
 r[@"supports_raytracing_selector"]=@([d respondsToSelector:@selector(supportsRaytracing)]);if([d respondsToSelector:@selector(supportsRaytracing)])r[@"supports_raytracing"]=@(d.supportsRaytracing);
 r[@"metal4_command_queue_selector"]=@([d respondsToSelector:NSSelectorFromString(@"newMTL4CommandQueue")]);
 if([d respondsToSelector:NSSelectorFromString(@"newMTL4CommandQueue")]){@try{id queue=[d newMTL4CommandQueue];r[@"metal4_queue_created"]=@(queue!=nil);if(queue)r[@"metal4_queue_class"]=NSStringFromClass([queue class]);}@catch(NSException*e){r[@"metal4_queue_exception"]=e.reason?:@"unknown";}}
 NSString*src=@"#include <metal_stdlib>\nusing namespace metal; kernel void test(device const float*x [[buffer(0)]],device float*y [[buffer(1)]],uint i [[thread_position_in_grid]]){y[i]=2*x[i]+1;}";
 NSMutableArray*tests=[NSMutableArray new];for(int lang:{0x10001,0x10002,0x20000,0x20001,0x20002,0x20003,0x20004,0x30000,0x30001,0x30002,0x40000}){NSMutableDictionary*t=[execute(d,src,lang) mutableCopy];t[@"language"]=[NSString stringWithFormat:@"%d.%d",lang>>16,lang&0xffff];[tests addObject:t];}r[@"language_tests"]=tests;
 NSData*json=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(json.bytes,1,json.length,stdout);puts("");return 0;
}}
