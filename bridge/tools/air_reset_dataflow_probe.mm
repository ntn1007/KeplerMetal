// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#include "NativeCommandBoundaryCapture.inc"
#include <cstdio>
struct Context {uint32_t magic,version,capacity,bytes;uint64_t records,reserved;};
static_assert(sizeof(Context)==32,"Context ABI");
static void need(bool ok,const char*why){if(!ok)@throw [NSException exceptionWithName:@"ProbeFailure" reason:@(why) userInfo:nil];}
static void emit(id v){NSData*d=[NSJSONSerialization dataWithJSONObject:v options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}
static NSArray *cases(){return @[
 @[@"empty",@0,@16,@7,@0,@32],@[@"single",@1,@1,@0,@0,@1],
 @[@"prefix",@7,@16,@3,@0,@8],@[@"full",@16,@16,@9,@0,@32],
 @[@"branch",@16,@16,@1,@1,@32],@[@"mask3",@37,@7,@29,@3,@64],
 @[@"tail",@37,@16,@17,@0,@32],@[@"bad_magic",@16,@16,@11,@0,@32],
 @[@"null_context",@16,@16,@11,@0,@32],@[@"large_capacity",@16,@17,@11,@0,@32],
 @[@"bad_size",@16,@16,@11,@0,@32],@[@"null_records",@16,@16,@11,@0,@32],
 @[@"unaligned_records",@16,@16,@11,@0,@32],@[@"bad_version",@16,@16,@11,@0,@32],
 @[@"reserved",@16,@16,@11,@0,@32],@[@"zero_capacity",@16,@0,@11,@0,@32]
#if KP_AIR_RENDER_DRAW
 ,@[@"draw_only",@16,@16,@3,@0,@32],@[@"ordered_reset",@16,@16,@3,@0,@32],@[@"ordered_draw",@16,@16,@3,@0,@32]
#endif
 ];}
int main(int argc,char**argv){@autoreleasepool{@try{
 need(argc==5,"library mode output certificate");NSString*mode=@(argv[2]),*out=@(argv[3]);
 need([@[@"inspect",@"execute",@"no_dispatch"]containsObject:mode],"Unknown mode");
#if KP_AIR_INSPECTION_ONLY
 need([mode isEqual:@"inspect"],"This host is restricted to construction-only inspection");
#endif
 id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(KPKepler880MIdentity(d)){need(!device,"Ambiguous device");device=d;}need(device,"GPU absent");
 NSError*error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])]error:&error];need(library,"Library refused");
 id<MTLFunction>function=[library newFunctionWithName:@"probe_boundary"];need(function,"Function absent");
 NSString*captures=[out stringByAppendingPathComponent:@"captures"];
 need([[NSFileManager defaultManager]createDirectoryAtPath:captures withIntermediateDirectories:NO attributes:nil error:&error],"Fresh captures required");
 need(beginCapture(captures),"Driver profile refused");id<MTLComputePipelineState>pso=nil;NSDictionary*capture=nil;
 @try{pso=[device newComputePipelineStateWithFunction:function error:&error];}@finally{capture=finishCapture();}
 need(pso&&[capture[@"constructor_restored"]boolValue],"Pipeline/restoration failed");NSArray*programs=capture[@"records"];need(programs.count==1,"One program required");
 NSDictionary*program=programs[0];need([program[@"post_constructor_code_saved"]boolValue],"Code absent");
 NSString*codeHash=program[@"post_constructor_code_SHA256"],*libraryHash=captureSHA([NSData dataWithContentsOfFile:@(argv[1])]);
 NSMutableDictionary*result=[@{@"mode":mode,@"device":device.name,@"registry_id":@(device.registryID),@"device_identity":KPKepler880MIdentity(device),@"capture":capture,@"library_SHA256":libraryHash,@"code_SHA256":codeHash,@"core_runtime_linked":@NO,@"trials":[NSMutableArray array],@"compute_dispatches":@0,@"command_buffers":@0}mutableCopy];
 if([mode isEqual:@"inspect"]){emit(result);return 0;}
 NSDictionary*cert=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[4])]options:0 error:&error];
 need([cert[@"library_SHA256"]isEqual:libraryHash]&&[cert[@"code_SHA256"]isEqual:codeHash]&&[cert[@"no_native_call"]boolValue],"Native certificate mismatch");
 id<MTLCommandQueue>queue=[device newCommandQueue];need(queue,"Queue absent");unsigned dispatches=0,buffers=0;
 for(NSArray*t in cases()){@autoreleasepool{
 NSString*name=t[0];uint32_t count=[t[1]unsignedIntValue],capacity=[t[2]unsignedIntValue],seed=[t[3]unsignedIntValue],mask=[t[4]unsignedIntValue],width=[t[5]unsignedIntValue];need(width<=pso.maxTotalThreadsPerThreadgroup,"Thread limit");
 NSMutableData*initial[3]={[NSMutableData dataWithLength:1152],[NSMutableData dataWithLength:384],[NSMutableData dataWithLength:384]};
 for(unsigned b=0;b<3;b++){uint8_t*v=(uint8_t*)initial[b].mutableBytes;for(size_t i=0;i<initial[b].length;i++)v[i]=(i<64||i>=initial[b].length-64)?uint8_t(0xa5+b):uint8_t(b==0?i*37+17:0x6d);}
 uint32_t*idx=(uint32_t*)((char*)initial[2].mutableBytes+64);for(unsigned i=0;i<64;i++)idx[i]=i<16?((((i&1)<<3)|((i&2)<<1)|((i&4)>>1)|((i&8)>>3))^(seed&15)):(i+16);
 id<MTLBuffer>gpu[3],upload[3],readback[3];for(unsigned i=0;i<3;i++){
 upload[i]=[device newBufferWithBytes:initial[i].bytes length:initial[i].length options:MTLResourceStorageModeShared];
 gpu[i]=[device newBufferWithLength:initial[i].length options:MTLResourceStorageModePrivate];readback[i]=[device newBufferWithLength:initial[i].length options:MTLResourceStorageModeShared];need(upload[i]&&gpu[i]&&readback[i],"Buffer allocation");}
 Context c={0x4b505243,1,capacity,64,gpu[0].gpuAddress+64,0};
 if([name isEqual:@"bad_magic"])c.magic^=1;if([name isEqual:@"bad_version"])c.version=2;if([name isEqual:@"bad_size"])c.bytes=32;
 if([name isEqual:@"reserved"])c.reserved=1;if([name isEqual:@"null_records"])c.records=0;if([name isEqual:@"unaligned_records"])c.records+=4;
 id<MTLBuffer>ctx=[device newBufferWithLength:32 options:MTLResourceStorageModePrivate],ctxUpload=[device newBufferWithBytes:&c length:32 options:MTLResourceStorageModeShared];
 uint64_t address=[name isEqual:@"null_context"]?0:ctx.gpuAddress;
 id<MTLBuffer>root=[device newBufferWithBytes:&address length:8 options:MTLResourceStorageModeShared];need(ctx&&ctxUpload&&root,"Context allocation");
 id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];
 for(unsigned i=0;i<3;i++)[blit copyFromBuffer:upload[i] sourceOffset:0 toBuffer:gpu[i] destinationOffset:0 size:initial[i].length];
 [blit copyFromBuffer:ctxUpload sourceOffset:0 toBuffer:ctx destinationOffset:0 size:32];[blit endEncoding];
 bool execute=![mode isEqual:@"no_dispatch"];
 if(execute){uint32_t config[4]={count,seed,mask,0};
#if KP_AIR_RENDER_DRAW
 config[3]=[name isEqual:@"ordered_reset"]?1u:[name isEqual:@"ordered_draw"]?2u:0u;
#endif
 id<MTLComputeCommandEncoder>enc=[cb computeCommandEncoder];[enc setComputePipelineState:pso];
 [enc setBuffer:root offset:0 atIndex:0];[enc setBuffer:gpu[1] offset:64 atIndex:1];[enc setBuffer:gpu[2] offset:64 atIndex:2];[enc setBytes:config length:16 atIndex:3];
 [enc useResource:ctx usage:MTLResourceUsageRead];[enc useResource:gpu[0] usage:MTLResourceUsageRead|MTLResourceUsageWrite];
 [enc dispatchThreadgroups:MTLSizeMake((count+width-1)/width?:1,1,1) threadsPerThreadgroup:MTLSizeMake(width,1,1)];[enc endEncoding];dispatches++;}
 blit=[cb blitCommandEncoder];for(unsigned i=0;i<3;i++)[blit copyFromBuffer:gpu[i] sourceOffset:0 toBuffer:readback[i] destinationOffset:0 size:initial[i].length];[blit endEncoding];
 [cb commit];[cb waitUntilCompleted];need(cb.status==MTLCommandBufferStatusCompleted&&!cb.error,"Command buffer failure");buffers++;
 unsigned privateCount=ctx.storageMode==MTLStorageModePrivate;
 NSMutableDictionary*files=[NSMutableDictionary dictionary];for(unsigned i=0;i<3;i++){
 privateCount+=gpu[i].storageMode==MTLStorageModePrivate;
 NSString*file=[NSString stringWithFormat:@"%@-%u.bin",name,i];NSData*data=[NSData dataWithBytes:readback[i].contents length:initial[i].length];need([data writeToFile:[out stringByAppendingPathComponent:file]atomically:YES],"Save readback");files[file]=captureSHA(data);
 [upload[i]release];[gpu[i]release];[readback[i]release];}
 [result[@"trials"]addObject:@{@"name":name,@"count":@(count),@"capacity":@(capacity),@"seed":@(seed),@"mask":@(mask),@"width":@(width),@"dispatched":@(execute),@"status":@(cb.status),@"private_buffers":@(privateCount),@"files":files}];
 [ctx release];[ctxUpload release];[root release];
 }}result[@"compute_dispatches"]=@(dispatches);result[@"command_buffers"]=@(buffers);emit(result);return 0;
 }@catch(NSException*e){emit(@{@"failure":e.reason?:e.name});return 1;}}}
