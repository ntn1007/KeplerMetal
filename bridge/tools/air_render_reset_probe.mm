// SPDX-License-Identifier: MIT
// Explicit project context, MRC capture ABI, native backend; no core archive.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#include "NativeCommandBoundaryCapture.inc"
#include <cstdio>
#include <vector>
struct Context { uint32_t magic,version,capacity,recordBytes;uint64_t records,reserved; };
static_assert(sizeof(Context)==32,"Project context ABI");
static void require(bool ok,const char *why){if(!ok)@throw [NSException exceptionWithName:@"ProbeFailure" reason:@(why) userInfo:nil];}
static void emit(id value){NSData *d=[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}
static NSArray *cases(){return @[
 @[@"prefix",@16,@3,@1],@[@"full",@16,@1,@32],@[@"small",@7,@1,@8],
 @[@"single",@1,@1,@1],@[@"over_index",@4,@7,@1],@[@"empty",@16,@0,@1],
 @[@"bad_magic",@16,@1,@32],@[@"bad_version",@16,@1,@32],
 @[@"zero_capacity",@0,@1,@32],@[@"large_capacity",@17,@1,@32],
 @[@"bad_size",@16,@1,@32],@[@"reserved",@16,@1,@32],
 @[@"null_records",@16,@1,@32],@[@"unaligned_records",@16,@1,@32],
 @[@"null_context",@16,@1,@32]];}
int main(int argc,char **argv){@autoreleasepool{@try{
 require(argc==5,"library mode output certificate");
 NSString *libraryPath=@(argv[1]),*mode=@(argv[2]),*out=@(argv[3]);
 require([@[@"inspect",@"execute",@"no_dispatch"]containsObject:mode],"Unknown mode");
 id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(KPKepler880MIdentity(d)){require(device==nil,"Ambiguous GPU");device=d;}
 require(device!=nil,"GTX PCI profile absent");
 NSError *error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:libraryPath]error:&error];
 require(library!=nil,"Library refused");id<MTLFunction>function=[library newFunctionWithName:@"probe_boundary"];require(function!=nil,"Function absent");
 NSString *capturePath=[out stringByAppendingPathComponent:@"captures"];
 require([[NSFileManager defaultManager]createDirectoryAtPath:capturePath withIntermediateDirectories:NO attributes:nil error:&error],"Fresh capture directory required");
 require(beginCapture(capturePath),"Driver capture profile refused");
 id<MTLComputePipelineState>pipeline=nil;NSDictionary *capture=nil;
 @try{pipeline=[device newComputePipelineStateWithFunction:function error:&error];}@finally{capture=finishCapture();}
 require(pipeline!=nil,"Native pipeline refused");require([capture[@"constructor_restored"]boolValue],"Observer restoration failed");
 NSArray *captured=capture[@"records"];require(captured.count==1,"Exactly one native program required");
 NSDictionary *program=captured[0];require([program[@"post_constructor_code_saved"]boolValue],"Native code missing");
 NSString *codeHash=program[@"post_constructor_code_SHA256"];
 NSString *libraryHash=captureSHA([NSData dataWithContentsOfFile:libraryPath]);
 NSMutableDictionary *result=[@{@"device":device.name,@"registry_id":@(device.registryID),@"device_identity":KPKepler880MIdentity(device),
 @"mode":mode,@"capture":capture,@"library_SHA256":libraryHash,@"code_SHA256":codeHash,@"core_runtime_linked":@NO,
 @"thread_width":@(pipeline.threadExecutionWidth),@"max_threads":@(pipeline.maxTotalThreadsPerThreadgroup),@"trials":[NSMutableArray array],@"compute_dispatches":@0,@"command_buffers":@0}mutableCopy];
 if([mode isEqual:@"inspect"]){emit(result);return 0;}
 NSDictionary *cert=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[4])]options:0 error:&error];
 require([cert[@"library_SHA256"]isEqual:libraryHash]&&[cert[@"code_SHA256"]isEqual:codeHash]&&[cert[@"no_native_call"]boolValue],"Exact offline certificate required");
 id<MTLCommandQueue>queue=[device newCommandQueue];require(queue!=nil,"Queue unavailable");unsigned dispatches=0,buffers=0;
 for(NSArray *test in cases()){@autoreleasepool{
 NSString *name=test[0];uint32_t capacity=[test[1]unsignedIntValue],groups=[test[2]unsignedIntValue],width=[test[3]unsignedIntValue];
 require(width<=pipeline.maxTotalThreadsPerThreadgroup,"Thread limit");
 NSMutableData *initial=[NSMutableData dataWithLength:1152];uint8_t *v=(uint8_t*)initial.mutableBytes;
 for(size_t i=0;i<initial.length;i++)v[i]=(i<64||i>=1088)?0xa5:uint8_t(i*37+17);
 id<MTLBuffer>upload=[device newBufferWithBytes:v length:1152 options:MTLResourceStorageModeShared];
 id<MTLBuffer>records=[device newBufferWithLength:1152 options:MTLResourceStorageModePrivate];
 id<MTLBuffer>readback=[device newBufferWithLength:1152 options:MTLResourceStorageModeShared];
 id<MTLBuffer>context=[device newBufferWithLength:32 options:MTLResourceStorageModePrivate];
 require(upload&&records&&readback&&context,"Allocation refused");
 Context c={0x4b505243,1,capacity,64,records.gpuAddress+64,0};
 if([name isEqual:@"bad_magic"])c.magic^=1;if([name isEqual:@"bad_version"])c.version=2;
 if([name isEqual:@"bad_size"])c.recordBytes=32;if([name isEqual:@"reserved"])c.reserved=1;
 if([name isEqual:@"null_records"])c.records=0;if([name isEqual:@"unaligned_records"])c.records+=4;
 id<MTLBuffer>contextUpload=[device newBufferWithBytes:&c length:32 options:MTLResourceStorageModeShared];
 uint64_t root=[name isEqual:@"null_context"]?0:context.gpuAddress;
 id<MTLBuffer>rootBuffer=[device newBufferWithBytes:&root length:8 options:MTLResourceStorageModeShared];require(contextUpload&&rootBuffer,"Root allocation");
 id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];
 [blit copyFromBuffer:upload sourceOffset:0 toBuffer:records destinationOffset:0 size:1152];
 [blit copyFromBuffer:contextUpload sourceOffset:0 toBuffer:context destinationOffset:0 size:32];[blit endEncoding];
 bool execute=groups&&!([mode isEqual:@"no_dispatch"]);
 if(execute){id<MTLComputeCommandEncoder>encoder=[cb computeCommandEncoder];[encoder setComputePipelineState:pipeline];
 [encoder setBuffer:rootBuffer offset:0 atIndex:0];[encoder useResource:context usage:MTLResourceUsageRead];
 [encoder useResource:records usage:MTLResourceUsageRead|MTLResourceUsageWrite];
 [encoder dispatchThreadgroups:MTLSizeMake(groups,1,1) threadsPerThreadgroup:MTLSizeMake(width,1,1)];[encoder endEncoding];dispatches++;}
 blit=[cb blitCommandEncoder];[blit copyFromBuffer:records sourceOffset:0 toBuffer:readback destinationOffset:0 size:1152];[blit endEncoding];
 [cb commit];[cb waitUntilCompleted];require(cb.status==MTLCommandBufferStatusCompleted&&!cb.error,"Command buffer failed");buffers++;
 NSData *data=[NSData dataWithBytes:readback.contents length:1152];NSString *file=[name stringByAppendingString:@".bin"];
 require([data writeToFile:[out stringByAppendingPathComponent:file] atomically:YES],"Readback save failed");
 [result[@"trials"]addObject:@{@"name":name,@"capacity":@(capacity),@"groups":@(groups),@"width":@(width),@"dispatched":@(execute),@"file":file,@"SHA256":captureSHA(data),@"status":@(cb.status),@"records_storage_mode":@(records.storageMode),@"context_storage_mode":@(context.storageMode)}];
 [upload release];[records release];[readback release];[context release];[contextUpload release];[rootBuffer release];
 }}
 result[@"compute_dispatches"]=@(dispatches);result[@"command_buffers"]=@(buffers);emit(result);return 0;
 }@catch(NSException *e){emit(@{@"failure":e.reason?:e.name});return 1;}}}
