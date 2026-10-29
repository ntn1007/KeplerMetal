// SPDX-License-Identifier: MIT
// Own-process validation of the incomplete-triangle state recheck.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerCPUICB.h"
#include <cstring>

static void need(BOOL ok,NSString*why){if(!ok)@throw [NSException exceptionWithName:@"StateGuardTest" reason:why userInfo:nil];}
static MTLRenderPassDescriptor* pass(id<MTLTexture> t){MTLRenderPassDescriptor*p=[MTLRenderPassDescriptor renderPassDescriptor];p.colorAttachments[0].texture=t;p.colorAttachments[0].loadAction=MTLLoadActionClear;p.colorAttachments[0].storeAction=MTLStoreActionStore;p.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);return p;}
int main(int argc,char**argv){@autoreleasepool{@try{
 need(argc==5,@"usage: client legacy.metallib vertex.metallib manifest.json output-directory");
 NSData*legacy=[NSData dataWithContentsOfFile:@(argv[1])],*vertex=[NSData dataWithContentsOfFile:@(argv[2])],*manifest=[NSData dataWithContentsOfFile:@(argv[3])];need(legacy&&vertex&&manifest,@"assets missing");
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();need(d&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"],@"device differs");id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 KPCPUICBScope*s=[KPCPUICBScope installRenderingOnDevice:d queue:q libraryData:legacy expectedSHA256:@"965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7" error:&error];need(s!=nil,error.description?:@"scope failed");
 need([s registerRenderVertexLibraryData:vertex expectedSHA256:@"c0e24e5a5534e10f0eca591b5ace2112d76eafde74ed297ce1b3df0d95b5ca43" manifestData:manifest expectedManifestSHA256:@"055fbb885cba637a2af12d9f4636b76ec6b2e9d437ce1c2e678395dc13065973" error:&error],error.description?:@"registration failed");
 id<MTLRenderPipelineState>original=[s renderPipeline],other=[s renderPipelineForName:@"smooth"];need(original&&other&&original!=other,@"pipeline identities differ");
 MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeDraw|MTLIndirectCommandTypeDrawIndexed;desc.maxVertexBufferBindCount=2;
 id<MTLIndirectCommandBuffer>commands=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared],copy=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared];need(commands&&copy,@"ICBs missing");
 uint16_t data[]={0,1,2};id<MTLBuffer>index=[d newBufferWithBytes:data length:sizeof(data) options:MTLResourceStorageModeShared],buffer=[d newBufferWithLength:256 options:MTLResourceStorageModeShared];need(index&&buffer,@"buffers missing");
 NSMutableArray*rows=[NSMutableArray new];
 for(NSString*which in @[@"pipeline",@"binding",@"indexed_pipeline",@"unchanged",@"restore",@"copy",@"complete"]){@autoreleasepool{
  [commands resetWithRange:NSMakeRange(0,1)];[copy resetWithRange:NSMakeRange(0,1)];id<MTLIndirectRenderCommand>c=[commands indirectRenderCommandAtIndex:0];[c setRenderPipelineState:original];
  BOOL indexed=[which isEqual:@"indexed_pipeline"],full=[which isEqual:@"complete"];
  if(indexed)[c drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:2 indexType:MTLIndexTypeUInt16 indexBuffer:index indexBufferOffset:0 instanceCount:1 baseVertex:0 baseInstance:0];
  else [c drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:full?3:2 instanceCount:1 baseInstance:0];
  if([which isEqual:@"copy"])need(KPCopyCPUICBCommands(commands,NSMakeRange(0,1),copy,0,&error),error.description?:@"copy failed");
  if([which isEqual:@"pipeline"]||indexed||[which isEqual:@"copy"]||[which isEqual:@"restore"])[c setRenderPipelineState:other];
  if([which isEqual:@"binding"])[c setVertexBuffer:buffer offset:0 atIndex:0];
  if([which isEqual:@"restore"])[c setRenderPipelineState:original];
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;
  id<MTLTexture>texture=[d newTextureWithDescriptor:td];id<MTLBuffer>out=[d newBufferWithLength:49664 options:MTLResourceStorageModeShared];need(texture&&out,@"output resources failed");memset(out.contents,0xa5,out.length);
  id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLRenderCommandEncoder>e=[s renderEncoderWithDescriptor:pass(texture) commandBuffer:cb error:&error];need(cb&&e,error.description?:@"encoder failed");
  BOOL expectedRefusal=[which isEqual:@"pipeline"]||[which isEqual:@"binding"]||indexed;BOOL refused=NO;
  @try{[e executeCommandsInBuffer:[which isEqual:@"copy"]?copy:commands withRange:NSMakeRange(0,1)];}
  @catch(NSException*x){refused=[x.name isEqual:@"KeplerCPUICBUnsupported"]&&[x.reason isEqual:@"Incomplete triangle state changed outside legacy profile"];}
  [e endEncoding];need(refused==expectedRefusal,@"state guard outcome differs");
  if(expectedRefusal){need(cb.status==MTLCommandBufferStatusNotEnqueued,@"refused buffer was submitted");[rows addObject:@{@"case":which,@"refused":@YES,@"submitted":@NO}];continue;}
  id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];[blit copyFromTexture:texture sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,48,1) toBuffer:out destinationOffset:256 destinationBytesPerRow:1024 destinationBytesPerImage:49152];[blit endEncoding];[cb commit];[cb waitUntilCompleted];need(cb.status==MTLCommandBufferStatusCompleted,cb.error.description?:@"GPU failed");
  const unsigned char*raw=(const unsigned char*)out.contents;for(NSUInteger i=0;i<256;i++)need(raw[i]==0xa5&&raw[out.length-1-i]==0xa5,@"guard changed");
  const float*px=(const float*)(raw+256);const float color[]={.75f,.125f,.25f,1.f};for(NSUInteger i=0;i<12288;i++)need(px[i]==(full?color[i%4]:0.f),@"pixel differs");
  NSString*file=[@(argv[4]) stringByAppendingPathComponent:[which stringByAppendingString:@".bin"]];need([[NSData dataWithBytes:raw length:out.length]writeToURL:[NSURL fileURLWithPath:file] options:NSDataWritingWithoutOverwriting error:&error],error.description?:@"capture failed");
  [rows addObject:@{@"case":which,@"refused":@NO,@"submitted":@YES,@"checked_channels":@12288,@"guard_bytes":@512}];
 }}
 [s restore];NSDictionary*result=@{@"status":@"PASS",@"device":d.name,@"registry_id":@(d.registryID),@"cases":rows};NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&error];need(json!=nil,@"json failed");fwrite(json.bytes,1,json.length,stdout);putchar('\n');return 0;
 }@catch(NSException*x){fprintf(stderr,"%s: %s\n",x.name.UTF8String,x.reason.UTF8String);return 1;}}}
