// SPDX-License-Identifier: MIT
// Observe native direct triangle vertex shader invocations; no Kepler hooks.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>
#include <string.h>
static void need(BOOL ok,NSString*why){if(!ok)@throw [NSException exceptionWithName:@"WitnessFailure" reason:why userInfo:nil];}
int main(){@autoreleasepool{@try{
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();need(d!=nil,@"no device");id<MTLCommandQueue>q=[d newCommandQueue];need(q!=nil,@"no queue");
 NSString*source=@"#include <metal_stdlib>\nusing namespace metal;\nvertex float4 vs(uint id [[vertex_id]], device atomic_uint *seen [[buffer(0)]]) { float2 p[5]={float2(-1,-1),float2(3,-1),float2(-1,3),float2(0,0),float2(1,1)}; if(id<5) atomic_fetch_or_explicit(seen,1u<<id,memory_order_relaxed); return float4(p[min(id,4u)],0,1); }\nfragment float4 fs(){return float4(1,0,0,1);}\n";
 NSError*err=nil;MTLCompileOptions*co=[MTLCompileOptions new];co.languageVersion=MTLLanguageVersion2_0;id<MTLLibrary>lib=[d newLibraryWithSource:source options:co error:&err];need(lib!=nil,err.description?:@"library failed");
 MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[lib newFunctionWithName:@"vs"];pd.fragmentFunction=[lib newFunctionWithName:@"fs"];pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;MTLRenderPipelineReflection*reflection=nil;id<MTLRenderPipelineState>p=[d newRenderPipelineStateWithDescriptor:pd options:MTLPipelineOptionArgumentInfo reflection:&reflection error:&err];need(p!=nil,err.description?:@"pipeline failed");
 NSMutableArray*args=[NSMutableArray new];for(MTLArgument*a in reflection.vertexArguments)[args addObject:@{@"name":a.name,@"index":@(a.index),@"access":@(a.access),@"type":@(a.type),@"active":@(a.active)}];
 NSMutableArray*rows=[NSMutableArray new];for(NSNumber*n in @[@0,@3,@4,@5]){@autoreleasepool{
  id<MTLBuffer>buf=[d newBufferWithLength:132 options:MTLResourceStorageModeShared];need(buf!=nil,@"buffer failed");memset(buf.contents,0xa5,buf.length);*((uint32_t*)((uint8_t*)buf.contents+64))=0;
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];td.usage=MTLTextureUsageRenderTarget;td.storageMode=MTLStorageModePrivate;id<MTLTexture>t=[d newTextureWithDescriptor:td];need(t!=nil,@"texture failed");
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor renderPassDescriptor];rp.colorAttachments[0].texture=t;rp.colorAttachments[0].loadAction=MTLLoadActionClear;rp.colorAttachments[0].storeAction=MTLStoreActionStore;rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
  id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:rp];need(e!=nil,@"encoder failed");[e setRenderPipelineState:p];[e setVertexBuffer:buf offset:64 atIndex:0];[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:n.unsignedIntegerValue];[e endEncoding];[cb commit];[cb waitUntilCompleted];need(cb.status==MTLCommandBufferStatusCompleted,cb.error.description?:@"command failed");
  uint8_t*b=(uint8_t*)buf.contents;BOOL guards=YES;for(NSUInteger i=0;i<64;i++)guards=guards&&b[i]==0xa5&&b[68+i]==0xa5;need(guards,@"guard changed");uint32_t mask=*((uint32_t*)(b+64));need(!(mask&~31u),@"unexpected mask bits");[rows addObject:@{@"count":n,@"mask":@(mask),@"guards":@YES,@"completed":@YES}];
 }}
 NSDictionary*out=@{@"device":d.name,@"registry_id":@(d.registryID),@"reflection":args,@"results":rows};NSData*j=[NSJSONSerialization dataWithJSONObject:out options:NSJSONWritingPrettyPrinted error:&err];need(j!=nil,@"JSON failed");fwrite(j.bytes,1,j.length,stdout);putchar('\n');return 0;
 }@catch(NSException*x){fprintf(stderr,"%s: %s\n",x.name.UTF8String,x.reason.UTF8String);return 1;}}}
