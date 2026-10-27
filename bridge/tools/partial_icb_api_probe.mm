// SPDX-License-Identifier: MIT
// Explicit opt-in integration test; no system driver or capability change.
#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <cstring>
#include <cstdlib>
#include <unistd.h>
struct Parameters { uint32_t count,seed,reserved0,reserved1; };
static void require(bool ok,NSString*s){if(!ok)@throw [NSException exceptionWithName:@"PartialICBProbeFailure" reason:s userInfo:nil];}
static bool complete(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static void save(NSData*d,NSString*p){require(d&&[d writeToFile:p atomically:YES],@"Cannot save evidence");}
static NSUInteger materials(NSArray*events){NSUInteger n=0;for(NSDictionary*e in events)if([e[@"operation"]isEqual:@"materialize_CPU_command"])n++;return n;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6)return 2;NSString*dir=@(argv[3]),*mode=@(argv[4]);char*end=nullptr;uint64_t rid=strtoull(argv[5],&end,10);if(!rid||!end||*end||(![mode isEqual:@"prepare"]&&![mode isEqual:@"execute"]))return 2;
 id<MTLDevice>d=nil;Class original=nil;KPCPUICBScope*scope=nil;NSMutableDictionary*report=[@{@"mode":mode,@"status":@"FAIL",@"pid":@(getpid()),@"system_modified":@NO,@"driver_modified":@NO,@"user_command_buffers":@0}mutableCopy];
 @try{
  for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==rid)d=x;require([d.name isEqual:@"NVIDIA GeForce GTX 880M"],@"GTX identity missing");original=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
  scope=[KPCPUICBScope installOnDevice:d queue:q libraryURL:[NSURL fileURLWithPath:@(argv[1])] expectedSHA256:@"1e89eaf47bdcb482e4fc760869b6005e47c1e836ec43e14820ba601c28fdd3f5" manifestURL:[NSURL fileURLWithPath:@(argv[2])] expectedManifestSHA256:@"31287315ccb87740c86c7180651007a766535bfcadf3de34edbe10e6bad233be" error:&error];require(scope!=nil,error.localizedDescription?:@"Scope failed");
  NSMutableDictionary*buffers=[NSMutableDictionary new];for(NSString*k in @[@"coordinates",@"geometry",@"counter"]){NSUInteger n=[k isEqual:@"counter"]?132:1024*16+128;id<MTLBuffer>gpu=[d newBufferWithLength:n options:MTLResourceStorageModePrivate],host=[d newBufferWithLength:n options:MTLResourceStorageModeManaged];require(gpu&&host,@"Output allocation failed");buffers[k]=gpu;buffers[[k stringByAppendingString:@"Host"]]=host;}
  id<MTLBuffer>p=[d newBufferWithLength:1536 options:MTLResourceStorageModeShared];require(p!=nil,@"Parameter buffer missing");memset(p.contents,0xa5,p.length);Parameters params={1024,0x3141,0,0};memcpy((char*)p.contents+256,&params,sizeof(params));buffers[@"p"]=p;
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=4;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:2 options:MTLResourceStorageModeShared],copy=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:2 options:MTLResourceStorageModeShared];require(icb&&copy,@"Project ICB missing");
  id<MTLIndirectComputeCommand>command=[icb indirectComputeCommandAtIndex:0];auto bind=[&](){[command setComputePipelineState:[scope pipelineForFunction:@"partial_builtin_barrier"]];for(unsigned i=0;i<4;i++)[command setKernelBuffer:buffers[@[@"coordinates",@"geometry",@"counter",@"p"][i]] offset:i==3?256:64 atIndex:i];};bind();NSMutableArray*negative=[NSMutableArray new];NSMutableDictionary*reasons=[NSMutableDictionary new];
  auto rejects=[&](NSString*name,void(^block)(void)){NSString*reason=nil;@try{block();}@catch(NSException*x){reason=x.reason;}NSString*wanted=[name isEqual:@"disabled"]?@"Fixed partial grid requires the explicitly enabled certified pipeline":@"Partial or zero thread grids are not implemented";require([reason containsString:wanted],[name stringByAppendingString:@" refusal reason differs"]);reasons[name]=reason;[negative addObject:name];};
  rejects(@"disabled",^{[command concurrentDispatchThreads:MTLSizeMake(11,7,5) threadsPerThreadgroup:MTLSizeMake(4,4,3)];});
  require([scope enableExperimentalPartialGridWithError:&error],error.localizedDescription?:@"Partial opt-in failed");
  rejects(@"wrong_grid",^{[command concurrentDispatchThreads:MTLSizeMake(12,7,5) threadsPerThreadgroup:MTLSizeMake(4,4,3)];});
  rejects(@"wrong_local",^{[command concurrentDispatchThreads:MTLSizeMake(11,7,5) threadsPerThreadgroup:MTLSizeMake(4,4,2)];});
  [command concurrentDispatchThreads:MTLSizeMake(11,7,5) threadsPerThreadgroup:MTLSizeMake(4,4,3)];
  error=nil;require(!KPCopyCPUICBCommands(icb,NSMakeRange(0,1),copy,0,&error)&&error,@"Partial copy was accepted");reasons[@"copy"]=error.localizedDescription;require([reasons[@"copy"]containsString:@"experimental partial command"],@"Copy refusal reason differs");[negative addObject:@"copy"];
  auto rejectedExecution=[&](NSString*name,NSRange range){id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];NSError*e2=nil;require([scope adaptComputeEncoder:e error:&e2],e2.localizedDescription?:@"Adapt failed");NSString*reason=nil;@try{[e executeCommandsInBuffer:icb withRange:range];}@catch(NSException*x){reason=x.reason;}[e endEncoding];NSString*wanted=[name isEqual:@"mixed_range"]?@"Partial grid accepts one command in a serial range":@"Partial grid requires the exact, nonaliasing qualified resource envelope";require([reason containsString:wanted],name);reasons[name]=reason;[negative addObject:name];};
  rejectedExecution(@"mixed_range",NSMakeRange(0,2));[command setKernelBuffer:buffers[@"coordinates"] offset:64 atIndex:1];rejectedExecution(@"alias",NSMakeRange(0,1));[command setKernelBuffer:buffers[@"geometry"] offset:64 atIndex:1];id<MTLBuffer>shortBuffer=[d newBufferWithLength:128 options:MTLResourceStorageModePrivate];[command setKernelBuffer:shortBuffer offset:64 atIndex:1];rejectedExecution(@"short_buffer",NSMakeRange(0,1));[command setKernelBuffer:buffers[@"geometry"] offset:64 atIndex:1];
  require(materials(scope.events)==0,@"Negative controls materialized commands");report[@"rejections"]=negative;report[@"rejection_reasons"]=reasons;
  auto initialize=[&](){id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];for(NSString*k in @[@"coordinates",@"geometry",@"counter"]){id<MTLBuffer>h=buffers[[k stringByAppendingString:@"Host"]];memset(h.contents,0xa5,h.length);if([k isEqual:@"counter"])memset((char*)h.contents+64,0,4);[h didModifyRange:NSMakeRange(0,h.length)];[b copyFromBuffer:h sourceOffset:0 toBuffer:buffers[k] destinationOffset:0 size:h.length];}[b endEncoding];require(complete(cb),@"Reset failed");};
  auto readback=[&](NSString*prefix){id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];for(NSString*k in @[@"coordinates",@"geometry",@"counter"]){id<MTLBuffer>h=buffers[[k stringByAppendingString:@"Host"]];[b copyFromBuffer:buffers[k] sourceOffset:0 toBuffer:h destinationOffset:0 size:h.length];[b synchronizeResource:h];}[b endEncoding];require(complete(cb),@"Readback failed");for(NSString*k in @[@"coordinates",@"geometry",@"counter"]){id<MTLBuffer>h=buffers[[k stringByAppendingString:@"Host"]];save([NSData dataWithBytes:h.contents length:h.length],[dir stringByAppendingPathComponent:[prefix stringByAppendingFormat:@".%@.bin",k]]);}};
  NSMutableArray*runs=[NSMutableArray new];report[@"runs"]=runs;unsigned n=[mode isEqual:@"execute"]?5:2;
  for(unsigned trial=0;trial<n;trial++){@autoreleasepool{
   if(trial==3)[command setKernelBuffer:buffers[@"geometry"] offset:64 atIndex:1];
   if(trial==4){[icb resetWithRange:NSMakeRange(0,1)];bind();[command concurrentDispatchThreads:MTLSizeMake(11,7,5) threadsPerThreadgroup:MTLSizeMake(4,4,3)];}
   initialize();id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];require([scope adaptComputeEncoder:e error:&error],error.localizedDescription?:@"Adapt failed");NSUInteger before=materials(scope.events);NSDictionary*proof=@{};
   if(trial){[e executeCommandsInBuffer:icb withRange:NSMakeRange(0,1)];NSDictionary*ev=scope.events.lastObject;require([ev[@"operation"]isEqual:@"execute_fixed_partial_grid"],@"Fixed partial event missing");proof=ev[@"evidence"];}
   [e endEncoding];NSUInteger after=materials(scope.events);readback([NSString stringWithFormat:@"trial-%u.pre",trial]);
   if([mode isEqual:@"prepare"]){[runs addObject:@{@"trial":@(trial),@"committed":@NO,@"materializations_before":@(before),@"materializations_after":@(after),@"proof":proof}];continue;}
   if(trial==4){[scope restore];require(object_getClass(d)==original,@"Early restore failed");command=nil;icb=nil;}
   require(complete(cb),@"User command buffer failed");if(trial)report[@"user_command_buffers"]=@([report[@"user_command_buffers"]unsignedIntValue]+1);readback([NSString stringWithFormat:@"trial-%u.post",trial]);
   [runs addObject:@{@"trial":@(trial),@"committed":@YES,@"command_status":@(cb.status),@"materializations_before":@(before),@"materializations_after":@(after),@"scope_restored_before_commit":@(trial==4),@"proof":proof}];
  }}
  [scope restore];report[@"scope_restored"]=@(object_getClass(d)==original);require(object_getClass(d)==original,@"Scope restore failed");report[@"device"]=d.name;report[@"registry_id"]=@(d.registryID);report[@"status"]=@"PASS";
 }@catch(NSException*x){if(scope)[scope restore];report[@"scope_restored"]=@(d&&original&&object_getClass(d)==original);report[@"reason"]=x.reason?:@"";}
 NSData*j=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return [report[@"status"]isEqual:@"PASS"]?0:1;
}}
