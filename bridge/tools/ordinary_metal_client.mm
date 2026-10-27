// SPDX-License-Identifier: MIT
// Independently compiled client: public Foundation and Metal APIs only.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <cstring>

extern "C" NSDictionary*ordinary_metal_render(id<MTLDevice>device,id<MTLCommandQueue>queue,
 id<MTLRenderPipelineState>pipeline,NSString*directory,NSString*mode){@autoreleasepool{@try{
 BOOL icb=([mode hasPrefix:@"auto"]&&![mode isEqual:@"auto_direct"])||[mode isEqual:@"no_auto"];BOOL drawICB=icb&&![mode isEqual:@"no_auto"];
 BOOL unsupported=[mode isEqual:@"unsupported"];NSUInteger count=[mode isEqual:@"auto_multiple"]?3:1,width=unsupported?32:64,height=unsupported?32:48;
 id<MTLIndirectCommandBuffer>commands=nil;
 if(icb||unsupported){MTLIndirectCommandBufferDescriptor*d=[MTLIndirectCommandBufferDescriptor new];d.commandTypes=MTLIndirectCommandTypeDraw;d.inheritBuffers=NO;d.inheritPipelineState=NO;d.maxVertexBufferBindCount=0;d.maxFragmentBufferBindCount=0;commands=[device newIndirectCommandBufferWithDescriptor:d maxCommandCount:1 options:MTLResourceStorageModeShared];if(!commands)return @{@"failure":@"ICB creation"};id<MTLIndirectRenderCommand>c=[commands indirectRenderCommandAtIndex:0];[c setRenderPipelineState:pipeline];[c drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1 baseInstance:0];}
 id<MTLCommandBuffer>cb=[queue commandBuffer];if(!cb)return @{@"failure":@"command buffer"};NSString*cbClass=NSStringFromClass(object_getClass(cb));
 // A compute encoder remains ordinary when only rendering adaptation is enabled.
 id<MTLComputeCommandEncoder>compute=[cb computeCommandEncoder];if(!compute)return @{@"failure":@"compute encoder"};NSString*computeClass=NSStringFromClass(object_getClass(compute));[compute endEncoding];
 NSMutableArray*buffers=[NSMutableArray new],*classes=[NSMutableArray new],*exceptions=[NSMutableArray new];BOOL unsupportedICBRefused=NO,unsupportedIndirectRefused=NO;
 for(NSUInteger i=0;i<count;i++){
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:width height:height mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>texture=[device newTextureWithDescriptor:td];if(!texture)return @{@"failure":@"texture"};
  MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=texture;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionStore;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
  id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:pass];if(!e)return @{@"failure":@"render encoder"};[classes addObject:NSStringFromClass(object_getClass(e))];[e setRenderPipelineState:pipeline];
  if(unsupported){@try{[e executeCommandsInBuffer:commands withRange:NSMakeRange(0,1)];}@catch(NSException*x){unsupportedICBRefused=YES;[exceptions addObject:@{@"name":x.name?:@"",@"reason":x.reason?:@""}];}id<MTLBuffer>range=[device newBufferWithLength:16 options:MTLResourceStorageModeShared];if(!range)return @{@"failure":@"indirect range"};@try{[e executeCommandsInBuffer:commands indirectBuffer:range indirectBufferOffset:0];}@catch(NSException*x){unsupportedIndirectRefused=YES;[exceptions addObject:@{@"name":x.name?:@"",@"reason":x.reason?:@""}];}if(!unsupportedICBRefused||!unsupportedIndirectRefused)return @{@"failure":@"unsupported project ICB not refused"};}
  if(drawICB)[e executeCommandsInBuffer:commands withRange:NSMakeRange(0,1)];else if(!icb)[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1 baseInstance:0];[e endEncoding];
  NSUInteger bytes=width*height*16;id<MTLBuffer>out=[device newBufferWithLength:bytes+512 options:MTLResourceStorageModeShared];if(!out)return @{@"failure":@"readback"};memset(out.contents,0xa5,out.length);id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];if(!b)return @{@"failure":@"blit"};[b copyFromTexture:texture sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(width,height,1) toBuffer:out destinationOffset:256 destinationBytesPerRow:width*16 destinationBytesPerImage:bytes];[b endEncoding];[buffers addObject:out];
 }
 [cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted)return @{@"failure":cb.error.description?:@"GPU completion"};
 for(NSUInteger i=0;i<buffers.count;i++){id<MTLBuffer>b=buffers[i];NSString*file=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"frame-%lu.bin",(unsigned long)i]];if([[NSFileManager defaultManager]fileExistsAtPath:file]||![[NSData dataWithBytes:b.contents length:b.length]writeToFile:file atomically:YES])return @{@"failure":@"save"};}
 return @{@"status":@"PASS",@"mode":mode,@"frames":@(count),@"width":@(width),@"height":@(height),@"unsupported_exceptions":exceptions,@"unsupported_ICB_refused":@(unsupportedICBRefused),@"unsupported_indirect_refused":@(unsupportedIndirectRefused),@"did_execute_icb":@(drawICB),@"used_standard_direct_draw":@(!icb),@"command_status":@(cb.status),@"command_buffer_class":cbClass,@"compute_encoder_class":computeClass,@"render_encoder_classes":classes};
 }@catch(NSException*x){return @{@"failure":x.reason?:@"exception"};}}}
