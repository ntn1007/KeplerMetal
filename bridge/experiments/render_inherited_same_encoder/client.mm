// SPDX-License-Identifier: MIT
// Exercise inherited ICB pipeline changes and subsequent ordinary draw state.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerCPUICB.h"
#include <cstring>
static void need(BOOL ok,NSString*why){if(!ok)@throw [NSException exceptionWithName:@"InheritedEncoderTest" reason:why userInfo:nil];}
struct Vertex{float p[4],c[4];};
static MTLRenderPassDescriptor*pass(id<MTLTexture>t){MTLRenderPassDescriptor*p=[MTLRenderPassDescriptor renderPassDescriptor];p.colorAttachments[0].texture=t;p.colorAttachments[0].loadAction=MTLLoadActionClear;p.colorAttachments[0].storeAction=MTLStoreActionStore;p.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);return p;}
int main(int argc,char**argv){@autoreleasepool{@try{
 need(argc==6,@"usage: client legacy vertex manifest output direct|auto");NSString*mode=@(argv[5]);BOOL automatic=[mode isEqual:@"auto"];need(automatic||[mode isEqual:@"direct"],@"mode differs");
 NSData*legacy=[NSData dataWithContentsOfFile:@(argv[1])],*vertex=[NSData dataWithContentsOfFile:@(argv[2])],*manifest=[NSData dataWithContentsOfFile:@(argv[3])];need(legacy&&vertex&&manifest,@"assets missing");
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();need(d&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"],@"device differs");id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 KPCPUICBScope*s=[KPCPUICBScope installRenderingOnDevice:d queue:q libraryData:legacy expectedSHA256:@"965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7" error:&error];need(s!=nil,error.description?:@"scope failed");
 need([s registerRenderVertexLibraryData:vertex expectedSHA256:@"c0e24e5a5534e10f0eca591b5ace2112d76eafde74ed297ce1b3df0d95b5ca43" manifestData:manifest expectedManifestSHA256:@"055fbb885cba637a2af12d9f4636b76ec6b2e9d437ce1c2e678395dc13065973" error:&error],error.description?:@"registration failed");
 id<MTLRenderPipelineState>smooth=[s renderPipelineForName:@"smooth"],flat=[s renderPipelineForName:@"flat"];need(smooth&&flat&&smooth!=flat,@"pipelines missing");
 Vertex v[4]={},parent[4]={};float points[4][2]={{0,0},{-1,-1},{3,-1},{-1,3}};for(int i=0;i<4;i++){v[i].p[0]=points[i][0];v[i].p[1]=points[i][1];v[i].p[2]=.5;v[i].p[3]=1;v[i].c[(i-1+3)%3]=1;v[i].c[3]=1;parent[i]=v[i];parent[i].c[0]=0;parent[i].c[1]=1;parent[i].c[2]=0;}
 float instance[4]={};id<MTLBuffer>vertices=[d newBufferWithBytes:v length:sizeof(v) options:MTLResourceStorageModeShared],caller=[d newBufferWithBytes:parent length:sizeof(parent) options:MTLResourceStorageModeShared],offsets=[d newBufferWithBytes:instance length:sizeof(instance) options:MTLResourceStorageModeShared];need(vertices&&caller&&offsets,@"buffers missing");
 MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeDraw;desc.maxVertexBufferBindCount=2;desc.inheritBuffers=NO;desc.inheritPipelineState=YES;
 id<MTLIndirectCommandBuffer>commands=automatic?[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared]:nil;need(!automatic||commands,@"ICB missing");
 if(automatic){id<MTLIndirectRenderCommand>c=[commands indirectRenderCommandAtIndex:0];[c setVertexBuffer:vertices offset:0 atIndex:0];[c setVertexBuffer:offsets offset:0 atIndex:1];[c drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:1 vertexCount:3 instanceCount:1 baseInstance:0];}
 MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>t=[d newTextureWithDescriptor:td];id<MTLBuffer>out=[d newBufferWithLength:49664 options:MTLResourceStorageModeShared];need(t&&out,@"output missing");memset(out.contents,0xa5,out.length);
 id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLRenderCommandEncoder>e=[s renderEncoderWithDescriptor:pass(t) commandBuffer:cb error:&error];need(e!=nil,error.description?:@"encoder failed");[e setVertexBuffer:caller offset:0 atIndex:0];[e setVertexBuffer:offsets offset:0 atIndex:1];
 NSArray*names=@[@"smooth",@"flat",@"smooth"];for(NSUInteger i=0;i<3;i++){
  [e setRenderPipelineState:i==1?flat:smooth];[e setScissorRect:(MTLScissorRect){i*16,0,16,48}];
  if(automatic)[e executeCommandsInBuffer:commands withRange:NSMakeRange(0,1)];else{[e setVertexBuffer:vertices offset:0 atIndex:0];[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:1 vertexCount:3 instanceCount:1 baseInstance:0];[e setVertexBuffer:caller offset:0 atIndex:0];}
 }
 // No pipeline or vertex rebinding: verifies state preserved after the ICB.
 [e setScissorRect:(MTLScissorRect){48,0,16,48}];[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:1 vertexCount:3 instanceCount:1 baseInstance:0];[e endEncoding];
 id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromTexture:t sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,48,1) toBuffer:out destinationOffset:256 destinationBytesPerRow:1024 destinationBytesPerImage:49152];[b endEncoding];[cb commit];[cb waitUntilCompleted];need(cb.status==MTLCommandBufferStatusCompleted,cb.error.description?:@"GPU failed");
 const uint8_t*raw=(const uint8_t*)out.contents;for(NSUInteger i=0;i<256;i++)need(raw[i]==0xa5&&raw[out.length-1-i]==0xa5,@"guard changed");
 NSString*file=[@(argv[4]) stringByAppendingPathComponent:@"image.bin"];need([[NSData dataWithBytes:raw length:out.length]writeToURL:[NSURL fileURLWithPath:file] options:NSDataWritingWithoutOverwriting error:&error],error.description?:@"capture failed");
 NSArray*events=s.events;[s restore];NSDictionary*result=@{@"status":@"PASS",@"device":d.name,@"registry_id":@(d.registryID),@"mode":mode,@"cases":@[@{@"pipelines":names,@"completed":@YES,@"guard_bytes":@512,@"same_encoder":@YES,@"followup_direct_draw":@YES}],@"events":events};NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&error];need(json!=nil,@"json failed");fwrite(json.bytes,1,json.length,stdout);putchar('\n');return 0;
 }@catch(NSException*x){fprintf(stderr,"%s: %s\n",x.name.UTF8String,x.reason.UTF8String);return 1;}}}
