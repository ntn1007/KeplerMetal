// SPDX-License-Identifier: MIT
// Pinned construction and bounded compute-only test. This is not Metal ICB ABI.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#include "NativeCommandBoundaryCapture.inc"
#include <cstdio>
#include <cstring>

struct Header {uint32_t magic,version,count,bytes;uint64_t records,reserved;};
struct Extension {uint32_t magic,version,count,bytes;uint64_t table,reserved;};
struct Row {uint64_t source,destination,token;uint32_t slot,reserved;};
static_assert(sizeof(Header)==32 && sizeof(Extension)==32 && sizeof(Row)==32,"Wire ABI");
static void need(bool ok,const char*why){if(!ok)@throw [NSException exceptionWithName:@"ProbeFailure" reason:@(why) userInfo:nil];}
static void emit(id v){NSData*d=[NSJSONSerialization dataWithJSONObject:v options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{@try{
 need(argc==5,"library mode output certificate");NSString*mode=@(argv[2]),*out=@(argv[3]);
 need([@[@"active",@"wrong_token",@"foreign_source",@"wrong_slot",@"row_reserved",@"bad_extension",@"bad_header",@"no_dispatch"]containsObject:mode],"Unknown mode");
 id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(KPKepler880MIdentity(d)){need(!device,"Ambiguous device");device=d;}need(device,"GPU absent");
 NSError*error=nil;id<MTLLibrary>lib=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])]error:&error];id<MTLFunction>f=[lib newFunctionWithName:@"probe_boundary"];need(f,"Library/function refused");
 NSString*captures=[out stringByAppendingPathComponent:@"captures"];need([[NSFileManager defaultManager]createDirectoryAtPath:captures withIntermediateDirectories:NO attributes:nil error:&error],"Fresh captures required");
 need(beginCapture(captures),"Driver profile refused");id<MTLComputePipelineState>pso=nil;NSDictionary*capture=nil;
 @try{pso=[device newComputePipelineStateWithFunction:f error:&error];}@finally{capture=finishCapture();}
 need(pso&&[capture[@"constructor_restored"]boolValue],"Pipeline/restoration failed");NSArray*programs=capture[@"records"];need(programs.count==1,"Expected one program");
 NSString*codeHash=programs[0][@"post_constructor_code_SHA256"],*libHash=captureSHA([NSData dataWithContentsOfFile:@(argv[1])]);
 NSDictionary*cert=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[4])]options:0 error:&error];
 need([cert[@"library_SHA256"]isEqual:libHash]&&[cert[@"code_SHA256"]isEqual:codeHash]&&[cert[@"no_native_call"]boolValue],"Native certificate mismatch");
 id<MTLCommandQueue>queue=[device newCommandQueue];id<MTLCommandBuffer>cb=[queue commandBuffer];need(queue&&cb,"Queue absent");
 id<MTLBuffer>records=[device newBufferWithLength:192 options:MTLResourceStorageModePrivate];
 id<MTLBuffer>context=[device newBufferWithLength:224 options:MTLResourceStorageModePrivate];
 need(records&&context&&records.gpuAddress&&context.gpuAddress&&!(records.gpuAddress>>40)&&!(context.gpuAddress>>40),"Private allocation");
 NSMutableData*initial=[NSMutableData dataWithLength:192];memset(initial.mutableBytes,0xa5,192);memset((char*)initial.mutableBytes+64,0x5a,64);
 uint64_t source=0x101;memcpy((char*)initial.mutableBytes+96,&source,8);
 NSMutableData*ctx=[NSMutableData dataWithLength:224];memset(ctx.mutableBytes,0xa5,224);
 Header h={0x4b505243,1,1,64,records.gpuAddress+64,0};Extension ext={0x4b505050,1,1,32,context.gpuAddress+128,0};Row row={0x101,0x202,0x11111,0,0};
 if([mode isEqual:@"bad_header"])h.magic^=1;if([mode isEqual:@"bad_extension"])ext.magic^=1;
 if([mode isEqual:@"foreign_source"])row.source=0x303;if([mode isEqual:@"wrong_slot"])row.slot=1;if([mode isEqual:@"row_reserved"])row.reserved=1;
 memcpy((char*)ctx.mutableBytes+64,&h,32);memcpy((char*)ctx.mutableBytes+96,&ext,32);memcpy((char*)ctx.mutableBytes+128,&row,32);
 uint64_t rootWords[2]={context.gpuAddress+64,[mode isEqual:@"wrong_token"]?0x22222u:0x11111u};
 id<MTLBuffer>root=[device newBufferWithBytes:rootWords length:16 options:MTLResourceStorageModeShared];
 id<MTLBuffer>input=[device newBufferWithBytes:initial.bytes length:192 options:MTLResourceStorageModeShared];
 id<MTLBuffer>ctxInput=[device newBufferWithBytes:ctx.bytes length:224 options:MTLResourceStorageModeShared];
 id<MTLBuffer>readback=[device newBufferWithLength:192 options:MTLResourceStorageModeShared];
 id<MTLBuffer>witness=[device newBufferWithLength:132 options:MTLResourceStorageModeShared];need(root&&input&&ctxInput&&readback&&witness,"Shared allocation");
 memset(witness.contents,0xa5,132);memset((char*)witness.contents+64,0x6d,4);
 id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];need(blit,"Upload encoder");[blit copyFromBuffer:input sourceOffset:0 toBuffer:records destinationOffset:0 size:192];[blit copyFromBuffer:ctxInput sourceOffset:0 toBuffer:context destinationOffset:0 size:224];[blit endEncoding];
 BOOL dispatched=![mode isEqual:@"no_dispatch"];
 if(dispatched){id<MTLComputeCommandEncoder>enc=[cb computeCommandEncoder];need(enc,"Compute encoder");[enc setComputePipelineState:pso];[enc setBuffer:root offset:0 atIndex:0];[enc setBuffer:witness offset:64 atIndex:1];[enc useResource:context usage:MTLResourceUsageRead];[enc useResource:records usage:MTLResourceUsageRead|MTLResourceUsageWrite];[enc dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];[enc endEncoding];}
 blit=[cb blitCommandEncoder];need(blit,"Readback encoder");[blit copyFromBuffer:records sourceOffset:0 toBuffer:readback destinationOffset:0 size:192];[blit endEncoding];[cb commit];[cb waitUntilCompleted];need(cb.status==MTLCommandBufferStatusCompleted&&!cb.error,"GPU command buffer failed");
 NSData*result=[NSData dataWithBytes:readback.contents length:192],*w=[NSData dataWithBytes:witness.contents length:132];
 need([result writeToFile:[out stringByAppendingPathComponent:@"records.bin"]atomically:YES]&&[w writeToFile:[out stringByAppendingPathComponent:@"witness.bin"]atomically:YES],"Output write failed");
 emit(@{@"mode":mode,@"device":device.name,@"registry_id":@(device.registryID),@"device_identity":KPKepler880MIdentity(device),@"capture":capture,@"library_SHA256":libHash,@"code_SHA256":codeHash,@"compute_dispatches":@(dispatched?1:0),@"command_buffers":@1,@"command_status":@(cb.status),@"records_SHA256":captureSHA(result),@"witness_SHA256":captureSHA(w),@"core_runtime_linked":@NO});
 [root release];[input release];[ctxInput release];[readback release];[witness release];[records release];[context release];[queue release];[pso release];[f release];[lib release];return 0;
 }@catch(NSException*e){emit(@{@"failure":e.reason?:e.name});return 1;}}}
