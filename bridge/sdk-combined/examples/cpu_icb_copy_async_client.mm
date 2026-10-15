// Public API adapted client: standard Metal blit-copy and ICB-execute selectors.
// Explicit scope preparation/adaptation; no private record API or KVC.
#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <cstring>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <chrono>
#ifndef KP_GPU_COPY_NATIVE
#define KP_GPU_COPY_NATIVE 0
#endif

struct NodeSpec { const char*function; unsigned local,groups; };
static const NodeSpec recipes[3][6]={
 {{"profile_integer",32,3},{"profile_fma",33,3},{"profile_shared",64,2},{"profile_fma",128,2},{"profile_shared",32,5},{"profile_integer",128,3}},
 {{"profile_fma",128,3},{"profile_shared",32,5},{"profile_integer",33,3},{"profile_shared",64,2},{"profile_integer",32,3},{"profile_fma",128,2}},
 {{"profile_shared",128,5},{"profile_integer",33,3},{"profile_fma",32,3},{"profile_integer",128,2},{"profile_fma",64,2},{"profile_shared",32,3}}
};
static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static void emit(id x){NSData*j=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6)return 1;NSString*libraryPath=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);NSUInteger local=strtoul(argv[4],nullptr,10),groups=strtoul(argv[5],nullptr,10);BOOL prep=[mode isEqual:@"prepare_async"],negative=[mode isEqual:@"no_second_async"],split=[mode isEqual:@"split_async"]||[mode isEqual:@"split_range_async"],rangeMode=[mode isEqual:@"range_async"]||[mode isEqual:@"split_range_async"];NSUInteger width=rangeMode?2:1,slots=width*3;
 if(![@[@"chain_async",@"range_async",@"split_async",@"split_range_async",@"no_second_async",@"prepare_async"]containsObject:mode]||(local!=32&&local!=33&&local!=128)||(groups!=3&&groups!=5)||local*groups>640)return 1;
 unsigned recipe=local==32?0:local==33?1:2;const NodeSpec*nodes=recipes[recipe];NSMutableArray*nodeRows=[NSMutableArray array];for(unsigned k=0;k<slots;k++)[nodeRows addObject:@{@"function":@(nodes[k].function),@"local":@(nodes[k].local),@"groups":@(nodes[k].groups)}];
 id<MTLDevice>d=nil;
#if KP_GPU_COPY_NATIVE
 d=MTLCreateSystemDefaultDevice();
#else
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;
#endif
 if(!d)return 2;Class before=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 NSMutableDictionary*pipelines=[NSMutableDictionary dictionary];
#if KP_GPU_COPY_NATIVE
 id<MTLLibrary>library=[d newLibraryWithURL:[NSURL fileURLWithPath:libraryPath]error:&error];
 for(NSString*name in @[@"profile_integer",@"profile_fma",@"profile_shared"]){MTLComputePipelineDescriptor*desc=[MTLComputePipelineDescriptor new];desc.computeFunction=[library newFunctionWithName:name];desc.supportIndirectCommandBuffers=YES;id<MTLComputePipelineState>p=[d newComputePipelineStateWithDescriptor:desc options:MTLPipelineOptionNone reflection:nil error:&error];if(!p)return 3;pipelines[name]=p;}
#else
 KPCPUICBScope*scope=[KPCPUICBScope installOnDevice:d queue:q libraryURL:[NSURL fileURLWithPath:libraryPath] expectedSHA256:@"913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd" error:&error];if(!scope){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}
 for(NSString*name in @[@"profile_integer",@"profile_fma",@"profile_shared"]){id<MTLComputePipelineState>p=[scope pipelineForFunction:name];if(!p)return 3;pipelines[name]=p;}

#endif
 NSMutableArray*runs=[NSMutableArray array];
 for(unsigned t=0;t<3;t++){@autoreleasepool{
  NSMutableArray*outputs=[NSMutableArray array],*counters=[NSMutableArray array],*params=[NSMutableArray array],*hostOut=[NSMutableArray array],*hostCount=[NSMutableArray array];
  uint32_t seeds[6];NSMutableArray*seedRows=[NSMutableArray array];for(unsigned k=0;k<slots;k++){seeds[k]=0x3311u+t*97u+k*0x4422u;[seedRows addObject:@(seeds[k])];}
  for(unsigned k=0;k<slots;k++){
   id<MTLBuffer>o=[d newBufferWithLength:10368 options:MTLResourceStorageModePrivate],c=[d newBufferWithLength:132 options:MTLResourceStorageModePrivate],p=[d newBufferWithLength:512 options:MTLResourceStorageModeShared],ho=[d newBufferWithLength:10368 options:MTLResourceStorageModeShared],hc=[d newBufferWithLength:132 options:MTLResourceStorageModeShared];if(!o||!c||!p||!ho||!hc)return 4;
   memset(ho.contents,0xa5,10368);memset(hc.contents,0xa5,132);uint32_t zero=0;memcpy((char*)hc.contents+64,&zero,4);memset(p.contents,0xa5,512);uint32_t words[4]={seeds[k],nodes[k].groups,nodes[k].local,640};memcpy(p.contents,words,16);
   [outputs addObject:o];[counters addObject:c];[params addObject:p];[hostOut addObject:ho];[hostCount addObject:hc];
  }
  id<MTLCommandBuffer>upload=[q commandBuffer];id<MTLBlitCommandEncoder>b=[upload blitCommandEncoder];for(unsigned k=0;k<slots;k++){[b copyFromBuffer:hostOut[k] sourceOffset:0 toBuffer:outputs[k] destinationOffset:0 size:10368];[b copyFromBuffer:hostCount[k] sourceOffset:0 toBuffer:counters[k] destinationOffset:0 size:132];}[b endEncoding];if(!done(upload))return 5;
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;desc.maxKernelBufferBindCount=3;
  id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:slots options:MTLResourceStorageModeShared];if(!icb)return 6;
  for(unsigned k=0;k<slots;k++){id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:k];[c setComputePipelineState:pipelines[@(nodes[k].function)]];[c setKernelBuffer:outputs[k] offset:64 atIndex:0];[c setKernelBuffer:counters[k] offset:64 atIndex:1];[c setKernelBuffer:params[k] offset:0 atIndex:2];[c concurrentDispatchThreadgroups:MTLSizeMake(nodes[k].groups,1,1)threadsPerThreadgroup:MTLSizeMake(nodes[k].local,1,1)];}
#if !KP_GPU_COPY_NATIVE
  if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots) error:&error]){fprintf(stderr,"%s\n",error.description.UTF8String);return 7;}
  NSUInteger eventStart=scope.events.count;
#endif
  auto readback=[&]()->BOOL{id<MTLCommandBuffer>r=[q commandBuffer];id<MTLBlitCommandEncoder>bl=[r blitCommandEncoder];for(unsigned k=0;k<slots;k++){[bl copyFromBuffer:outputs[k] sourceOffset:0 toBuffer:hostOut[k] destinationOffset:0 size:10368];[bl copyFromBuffer:counters[k] sourceOffset:0 toBuffer:hostCount[k] destinationOffset:0 size:132];}[bl endEncoding];return done(r);};
  if(!readback())return 10;for(unsigned k=0;k<slots;k++){id<MTLBuffer>ho=hostOut[k],hc=hostCount[k];for(NSUInteger i=0;i<10368;i++)if(((uint8_t*)ho.contents)[i]!=0xa5)return 10;uint32_t c=99;memcpy(&c,(char*)hc.contents+64,4);if(c)return 10;}
  id<MTLSharedEvent>gate=[d newSharedEvent];if(!gate)return 14;gate.signaledValue=0;uint32_t markerValue=0x61a00000u+t;id<MTLBuffer>marker=[d newBufferWithLength:32 options:MTLResourceStorageModeShared],markerInput=[d newBufferWithBytes:&markerValue length:4 options:MTLResourceStorageModeShared];if(!marker||!markerInput)return 14;memset(marker.contents,0xa5,32);uint32_t markerZero=0;memcpy((char*)marker.contents+16,&markerZero,4);
  std::mutex mutex;std::condition_variable wake;bool released=false;std::atomic<bool>watchdogFired(false);
  std::thread watchdog([&]{@autoreleasepool{std::unique_lock<std::mutex>lock(mutex);if(!wake.wait_for(lock,std::chrono::seconds(2),[&]{return released;})){watchdogFired.store(true);gate.signaledValue=1;}}});
  id<MTLCommandBuffer>producer=[q commandBuffer],middle=[q commandBuffer],main=split?[q commandBuffer]:middle;
  NSArray*copyEvents=nil;NSUInteger producerAtCopy=0,middleAtExecute=0,consumerBeforeCommit=99,producerBeforeRelease=0,middleBeforeRelease=0,consumerBeforeRelease=0;BOOL ownerAlive=NO;uint32_t markerBeforeCopy=99,markerBeforeRelease=99,markerFinal=99;
  @try{
   [producer encodeWaitForEvent:gate value:1];b=[producer blitCommandEncoder];
#if !KP_GPU_COPY_NATIVE
   if(![scope adaptBlitEncoder:b error:&error])return 8;
#endif
   [b copyFromBuffer:markerInput sourceOffset:0 toBuffer:marker destinationOffset:16 size:4];[b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(0,width)destination:icb destinationIndex:width];[b endEncoding];[producer commit];
   memcpy(&markerBeforeCopy,(char*)marker.contents+16,4);producerAtCopy=producer.status;if(markerBeforeCopy!=0||(producerAtCopy!=2&&producerAtCopy!=3)||gate.signaledValue!=0)return 15;
   b=[middle blitCommandEncoder];
#if !KP_GPU_COPY_NATIVE
   if(![scope adaptBlitEncoder:b error:&error])return 8;
#endif
   if(!negative)[b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(width,width)destination:icb destinationIndex:width*2];[b endEncoding];
   if(split){[middle commit];middleAtExecute=middle.status;if((middleAtExecute!=2&&middleAtExecute!=3)||gate.signaledValue!=0)return 15;}
   id<MTLComputeCommandEncoder>e=[main computeCommandEncoder];
#if !KP_GPU_COPY_NATIVE
   if(![scope adaptComputeEncoder:e error:&error])return 9;
#endif
   for(unsigned k=0;k<slots;k++){[e useResource:outputs[k]usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e useResource:counters[k]usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e useResource:params[k]usage:MTLResourceUsageRead];}
   [e executeCommandsInBuffer:icb withRange:NSMakeRange(width*2,width)];[e endEncoding];
#if KP_GPU_COPY_NATIVE
   copyEvents=@[];
#else
   copyEvents=[scope.events subarrayWithRange:NSMakeRange(eventStart,scope.events.count-eventStart)];
#endif
   __weak id<MTLBuffer>weakParameter=params[0];[params removeAllObjects];icb=nil;ownerAlive=weakParameter!=nil;if(!ownerAlive)return 10;
   consumerBeforeCommit=main.status;if(consumerBeforeCommit!=0)return 15;if(!prep)[main commit];
   producerBeforeRelease=producer.status;middleBeforeRelease=middle.status;consumerBeforeRelease=main.status;
   memcpy(&markerBeforeRelease,(char*)marker.contents+16,4);if(markerBeforeRelease!=0||(producerBeforeRelease!=2&&producerBeforeRelease!=3)||gate.signaledValue!=0||(!prep&&consumerBeforeRelease!=2&&consumerBeforeRelease!=3))return 15;
  }@catch(NSException*x){fprintf(stderr,"%s\n",x.reason.UTF8String);return 19;}
  @finally{gate.signaledValue=1;{std::lock_guard<std::mutex>lock(mutex);released=true;}wake.notify_all();watchdog.join();}
  if(watchdogFired.load()){fprintf(stderr,"Gate watchdog released the queue; asynchronous observation is invalid\n");return 16;}
  if(prep)[producer waitUntilCompleted];else [main waitUntilCompleted];
  if(producer.status!=MTLCommandBufferStatusCompleted||(!prep&&main.status!=MTLCommandBufferStatusCompleted)||(split&&middle.status!=MTLCommandBufferStatusCompleted))return 11;
  memcpy(&markerFinal,(char*)marker.contents+16,4);if(markerFinal!=markerValue)return 20;for(unsigned j=0;j<32;j++)if((j<16||j>=20)&&((uint8_t*)marker.contents)[j]!=0xa5)return 20;
  if(!readback())return 12;
  NSMutableArray*names=[NSMutableArray array];for(unsigned k=0;k<slots;k++)for(NSString*kind in @[@"output",@"counter"]){id<MTLBuffer>h=[kind isEqual:@"output"]?hostOut[k]:hostCount[k];NSString*name=[NSString stringWithFormat:@"trial-%u-%u-%@.bin",t,k,kind];if(![[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:name]atomically:YES])return 13;[names addObject:name];}
  [runs addObject:@{@"trial":@(t),@"seeds":seedRows,@"files":names,@"width":@(width),@"slots":@(slots),@"producer_committed":@YES,@"producer_marker_before_second_copy":@(markerBeforeCopy),@"producer_marker_before_gate_release":@(markerBeforeRelease),@"producer_marker_final":@(markerFinal),@"producer_marker_expected":@(markerValue),@"producer_marker_guards_intact":@YES,@"producer_status_at_second_copy":@(producerAtCopy),@"middle_committed_before_execute":@(split),@"middle_status_at_execute":@(middleAtExecute),@"consumer_status_before_commit":@(consumerBeforeCommit),@"producer_status_before_gate_release":@(producerBeforeRelease),@"middle_status_before_gate_release":@(middleBeforeRelease),@"consumer_status_before_gate_release":@(consumerBeforeRelease),@"producer_final_status":@(producer.status),@"middle_final_status":@(middle.status),@"consumer_final_status":@(main.status),@"consumer_committed":@(!prep),@"gate_initial_value":@0,@"gate_final_value":@(gate.signaledValue),@"gate_release_by_main":@YES,@"watchdog_fired":@(watchdogFired.load()),@"CPU_waits_between_producer_and_consumer_commits":@0,@"final_completion_wait_calls":@1,@"initial_output_readback_before_producer_commit":@YES,@"ICB_external_reference_released_before_commit":@YES,@"parameter_external_references_released_before_commit":@YES,@"source_parameter_alive_before_commit":@(ownerAlive),@"copy_events":copyEvents}];

 }}
#if KP_GPU_COPY_NATIVE
 NSArray*scopeEvents=@[];
#else
 [scope restore];NSArray*scopeEvents=scope.events;
#endif
 emit(@{@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),@"local":@(local),@"groups":@(groups),@"width":@(width),@"slots":@(slots),@"recipe":@(recipe),@"node_specs":nodeRows,@"runs":runs,@"scope_restored":@(object_getClass(d)==before),@"scope_events":scopeEvents,@"native_reference":@(KP_GPU_COPY_NATIVE!=0),@"system_modified":@NO,@"CPU_expected_answers_uploaded":@NO,@"intermediate_descriptor_CPU_readback":@NO,@"full_ICB_contract":@NO,@"performance_benchmark":@NO});return object_getClass(d)==before?0:14;
}}
