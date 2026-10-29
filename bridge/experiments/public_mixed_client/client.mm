// SPDX-License-Identifier: MIT
// Independently compiled client. Only public Foundation/Metal APIs are used.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstring>
struct Params {uint32_t mode,seed,pad0,pad1;};
extern "C" NSDictionary* run_public_mixed(id<MTLDevice>d,id<MTLCommandQueue>q,
 id<MTLComputePipelineState>cp,id<MTLRenderPipelineState>rp,NSString*out,NSString*mode){@autoreleasepool{@try{
 BOOL direct=[mode isEqual:@"direct"],noProducer=[mode isEqual:@"no-producer"],noRender=[mode isEqual:@"no-render"];
 if(!direct&&![mode isEqual:@"icb"]&&!noProducer&&!noRender)return @{@"error":@"mode"};
 id<MTLBuffer>indices=[d newBufferWithLength:128 options:MTLResourceStorageModePrivate],counter=[d newBufferWithLength:132 options:MTLResourceStorageModePrivate];
 id<MTLBuffer>params=[d newBufferWithLength:1536 options:MTLResourceStorageModeShared],ih=[d newBufferWithLength:128 options:MTLResourceStorageModeManaged],ch=[d newBufferWithLength:132 options:MTLResourceStorageModeManaged];
 if(!indices||!counter||!params||!ih||!ch)return @{@"error":@"buffers"};
 memset(ih.contents,0xa5,ih.length);uint32_t init[]={0,0,0,0x77777777};memcpy((char*)ih.contents+64,init,sizeof init);[ih didModifyRange:NSMakeRange(0,ih.length)];
 memset(ch.contents,0xa5,ch.length);uint32_t zero=0;memcpy((char*)ch.contents+64,&zero,4);[ch didModifyRange:NSMakeRange(0,ch.length)];
 memset(params.contents,0xa5,params.length);Params p={0,0x4521,0,0};memcpy((char*)params.contents+256,&p,sizeof p);
 id<MTLCommandBuffer>initCB=[q commandBuffer];id<MTLBlitCommandEncoder>ib=[initCB blitCommandEncoder];[ib copyFromBuffer:ih sourceOffset:0 toBuffer:indices destinationOffset:0 size:128];[ib copyFromBuffer:ch sourceOffset:0 toBuffer:counter destinationOffset:0 size:132];[ib endEncoding];[initCB commit];[initCB waitUntilCompleted];if(initCB.status!=MTLCommandBufferStatusCompleted)return @{@"error":@"initialization"};
 id<MTLIndirectCommandBuffer>ci=nil,ri=nil;
 if(!direct){MTLIndirectCommandBufferDescriptor*cd=[MTLIndirectCommandBufferDescriptor new];cd.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;cd.maxKernelBufferBindCount=3;cd.inheritBuffers=NO;cd.inheritPipelineState=NO;
  MTLIndirectCommandBufferDescriptor*rd=[MTLIndirectCommandBufferDescriptor new];rd.commandTypes=MTLIndirectCommandTypeDrawIndexed;rd.inheritBuffers=NO;rd.inheritPipelineState=NO;
  ci=[d newIndirectCommandBufferWithDescriptor:cd maxCommandCount:1 options:MTLResourceStorageModeShared];ri=[d newIndirectCommandBufferWithDescriptor:rd maxCommandCount:1 options:MTLResourceStorageModeShared];if(!ci||!ri)return @{@"error":@"ICB allocation"};
  if(!noProducer){id<MTLIndirectComputeCommand>c=[ci indirectComputeCommandAtIndex:0];[c setComputePipelineState:cp];[c setKernelBuffer:indices offset:64 atIndex:0];[c setKernelBuffer:counter offset:64 atIndex:1];[c setKernelBuffer:params offset:256 atIndex:2];[c concurrentDispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];}
  if(!noRender){id<MTLIndirectRenderCommand>r=[ri indirectRenderCommandAtIndex:0];[r setRenderPipelineState:rp];[r drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:3 indexType:MTLIndexTypeUInt32 indexBuffer:indices indexBufferOffset:64 instanceCount:1 baseVertex:0 baseInstance:0];}
 }
 MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>t=[d newTextureWithDescriptor:td];id<MTLBuffer>pixels=[d newBufferWithLength:49664 options:MTLResourceStorageModeShared];if(!t||!pixels)return @{@"error":@"image allocation"};memset(pixels.contents,0xa5,pixels.length);
 MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=t;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionStore;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
 id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>ce=[cb computeCommandEncoder];if(!ce)return @{@"error":@"compute encoder"};
 if(direct){[ce setComputePipelineState:cp];[ce setBuffer:indices offset:64 atIndex:0];[ce setBuffer:counter offset:64 atIndex:1];[ce setBuffer:params offset:256 atIndex:2];[ce dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];}else [ce executeCommandsInBuffer:ci withRange:NSMakeRange(0,1)];[ce endEncoding];
 id<MTLRenderCommandEncoder>re=[cb renderCommandEncoderWithDescriptor:pass];if(!re)return @{@"error":@"render encoder"};[re setScissorRect:MTLScissorRect{3,4,13,9}];
 if(direct){[re setRenderPipelineState:rp];[re drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:3 indexType:MTLIndexTypeUInt32 indexBuffer:indices indexBufferOffset:64 instanceCount:1 baseVertex:0 baseInstance:0];}else [re executeCommandsInBuffer:ri withRange:NSMakeRange(0,1)];[re endEncoding];
 id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromTexture:t sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,48,1) toBuffer:pixels destinationOffset:256 destinationBytesPerRow:1024 destinationBytesPerImage:49152];[b copyFromBuffer:indices sourceOffset:0 toBuffer:ih destinationOffset:0 size:128];[b copyFromBuffer:counter sourceOffset:0 toBuffer:ch destinationOffset:0 size:132];[b synchronizeResource:ih];[b synchronizeResource:ch];[b endEncoding];[cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted)return @{@"error":cb.error.description?:@"GPU completion"};
 for(NSArray*x in @[@[@"pixels.bin",pixels],@[@"indices.bin",ih],@[@"counter.bin",ch]]){NSString*path=[out stringByAppendingPathComponent:x[0]];id<MTLBuffer>buf=x[1];if([[NSFileManager defaultManager]fileExistsAtPath:path]||![[NSData dataWithBytes:buf.contents length:buf.length]writeToFile:path atomically:YES])return @{@"error":@"output"};}
 return @{@"status":@"PASS",@"mode":mode,@"command_status":@(cb.status),@"same_command_buffer":@YES,@"no_cpu_read_between_compute_render":@YES,@"did_use_icbs":@(!direct)};
 }@catch(NSException*x){return @{@"error":x.reason?:@"exception"};}}}
