// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include "KeplerCommandIR.h"
#include <cstring>
static void emit(id x){NSData*d=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}
static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char c:h)[s appendFormat:@"%02x",c];return s;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*library=@(argv[1]),*mode=@(argv[2]),*out=@(argv[3]);BOOL dispatch=[mode isEqual:@"execute"];if(!dispatch&&![mode isEqual:@"no_dispatch"])return 1;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(KPKepler880MIdentity(x)){if(d)return 2;d=x;}if(!d)return 2;
 NSError*error=nil;id<MTLLibrary>l=[d newLibraryWithURL:[NSURL fileURLWithPath:library]error:&error];id<MTLComputePipelineState>p=[d newComputePipelineStateWithFunction:[l newFunctionWithName:@"stable_pipeline_record_case"]error:&error];if(!p||p.threadExecutionWidth!=32)return 3;id<MTLCommandQueue>q=[d newCommandQueue];NSMutableArray*cases=[NSMutableArray new];
 Class original=object_getClass(d);NSString*assets=[library stringByDeletingLastPathComponent];
 auto setup=[&]()->KPCPUICBScope*{
  error=nil;
  auto bytes=[&](NSString*n){return[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:n]];};NSData*consumer=bytes(@"consumer.metallib"),*manifest=bytes(@"consumer.json");
  KPCPUICBScope*s=[KPCPUICBScope installOnDevice:d queue:q libraryData:consumer expectedSHA256:sha(consumer) manifestData:manifest expectedManifestSHA256:sha(manifest) error:&error];if(!s)return nil;
  for(NSArray*a in @[@[@"gpu_command_selector.metallib",@0],@[@"gpu_command_geometry.metallib",@1],@[@"gpu_command_bindings.metallib",@2],@[@"materializer.metallib",@3]]){NSData*b=bytes(a[0]);BOOL ok=NO;switch([a[1]intValue]){case 0:ok=[s enableGPUCommandSelectionWithLibraryData:b expectedSHA256:sha(b)error:&error];break;case 1:ok=[s enableGPUCommandGeometryWithLibraryData:b expectedSHA256:sha(b)error:&error];break;case 2:ok=[s enableGPUCommandBindingsWithLibraryData:b expectedSHA256:sha(b)error:&error];break;case 3:ok=[s enableGPUCommandIRv2WithLibraryData:b expectedSHA256:sha(b)error:&error];}if(!ok){[s restore];return nil;}}return s;
 };
 KPCPUICBScope*old=setup();uint64_t stale=[old commandIRIdentityForPipeline:[old pipelineForFunction:@"dependency_seed"]error:&error];if(!stale||error)return 7;id<MTLComputePipelineState>oldPipeline=[old pipelineForFunction:@"dependency_seed"];[old restore];error=nil;
 if([old commandIRIdentityForPipeline:oldPipeline error:&error]||!error)return 7;
 KPCPUICBScope*active=setup();error=nil;uint64_t first=[active commandIRIdentityForPipeline:[active pipelineForFunction:@"dependency_seed"]error:&error],second=[active commandIRIdentityForPipeline:[active pipelineForFunction:@"dependency_gather"]error:&error];
 if(!first||!second||error||first==second||first==stale||second==stale||first!=[active commandIRIdentityForPipeline:[active pipelineForFunction:@"dependency_seed"]error:&error])return 7;
 error=nil;if([active commandIRIdentityForPipeline:nil error:&error]||!error)return 7;error=nil;if([active commandIRIdentityForPipeline:p error:&error]||!error)return 7;
 const uint64_t ids[]={first,second,stale};
 for(uint32_t op=0;op<21;op++){@autoreleasepool{
  id<MTLBuffer>records=[d newBufferWithLength:512 options:MTLResourceStorageModePrivate],host=[d newBufferWithLength:512 options:MTLResourceStorageModeShared],context=[d newBufferWithLength:736 options:MTLResourceStorageModeShared],parameters=[d newBufferWithLength:256 options:MTLResourceStorageModePrivate];if(!records||!host||!context||!parameters)return 4;
  memset(host.contents,0xa5,512);memset(context.contents,0x5a,736);KPStableCommandContext c={};c.base={op==11?KP_COMMAND_CONTEXT_MAGIC:KP_COMMAND_STABLE_CONTEXT_MAGIC,3,2,4,records.gpuAddress+128,128,op==15?0u:op==16?9u:4u};
  const uint64_t identities[]={ids[0],ids[1],ids[0],ids[0]};const uint32_t offsets[]={64,128,192,64},locals[]={32,64,16,32},groups[]={2,8,16,op==13?2u:4u};
  for(unsigned i=0;i<4;i++){auto&e=c.pipelines[i];e.identity=identities[i];e.parameters_address=parameters.gpuAddress+offsets[i];e.groups[0]=groups[i];e.groups[1]=e.groups[2]=1;e.local[0]=locals[i];e.local[1]=e.local[2]=1;e.shared_bytes=(op==14&&i==3)||(op==20&&i==0)?16:0;e.constant_index=2;}
  memcpy((char*)context.contents+128,&c,sizeof c);NSData*before=[NSData dataWithBytes:context.contents length:736];id<MTLCommandBuffer>b=[q commandBuffer];id<MTLBlitCommandEncoder>blit=[b blitCommandEncoder];[blit copyFromBuffer:host sourceOffset:0 toBuffer:records destinationOffset:0 size:512];[blit endEncoding];
  if(dispatch){id<MTLComputeCommandEncoder>e=[b computeCommandEncoder];[e setComputePipelineState:p];[e setBuffer:context offset:128 atIndex:0];[e setBytes:ids length:sizeof ids atIndex:1];[e setBuffer:parameters offset:64 atIndex:2];[e setBytes:&op length:4 atIndex:3];[e useResource:records usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];}
  blit=[b blitCommandEncoder];[blit copyFromBuffer:records sourceOffset:0 toBuffer:host destinationOffset:0 size:512];[blit endEncoding];[b commit];[b waitUntilCompleted];if(b.status!=MTLCommandBufferStatusCompleted)return 5;
  NSString*f=[NSString stringWithFormat:@"case-%u-records.bin",op];[[NSData dataWithBytes:host.contents length:512]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];BOOL unchanged=memcmp(context.contents,before.bytes,736)==0;
  NSString*cf=[NSString stringWithFormat:@"case-%u-context.bin",op];[[NSData dataWithBytes:context.contents length:736]writeToFile:[out stringByAppendingPathComponent:cf]atomically:YES];
  [cases addObject:@{@"operation":@(op),@"file":f,@"context_file":cf,@"records_address":@(records.gpuAddress+128),@"command_status":@(b.status),@"context_and_guards_unchanged":@(unchanged),@"parameter_address":@(parameters.gpuAddress+64)}];if(!unchanged)return 6;
 }}
 [active restore];if(object_getClass(d)!=original)return 8;
 emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":KPKepler880MIdentity(d),@"mode":mode,@"cases":cases,@"current_pipeline_IDs":@[@(first),@(second)],@"stale_pipeline_ID":@(stale),@"identity_API_refusals":@3,@"scopes_restored":@YES,@"user_dispatches":dispatch?@21:@0,@"command_buffers":@21,@"record_execution":@NO,@"instruction_import":@NO,@"performance_benchmark":@NO,@"system_modified":@NO});return 0;
}}
