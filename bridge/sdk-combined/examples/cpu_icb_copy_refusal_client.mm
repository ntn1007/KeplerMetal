// Public API adapted client: standard Metal blit-copy and ICB-execute selectors.
// Explicit scope preparation/adaptation; no private record API or KVC.
#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <cstring>
#define KP_GPU_COPY_NATIVE 0

struct NodeSpec { const char*function; unsigned local,groups; };
static const NodeSpec recipes[3][6]={
 {{"profile_integer",32,3},{"profile_fma",33,3},{"profile_shared",64,2},{"profile_fma",128,2},{"profile_shared",32,5},{"profile_integer",128,3}},
 {{"profile_fma",128,3},{"profile_shared",32,5},{"profile_integer",33,3},{"profile_shared",64,2},{"profile_integer",32,3},{"profile_fma",128,2}},
 {{"profile_shared",128,5},{"profile_integer",33,3},{"profile_fma",32,3},{"profile_integer",128,2},{"profile_fma",64,2},{"profile_shared",32,3}}
};
static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static void emit(id x){NSData*j=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6)return 1;NSString*libraryPath=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);NSUInteger local=strtoul(argv[4],nullptr,10),groups=strtoul(argv[5],nullptr,10);NSUInteger width=2,slots=6;
 if(![@[@"second_unprepared",@"pending_source",@"overlap",@"unretained_CB"]containsObject:mode]||local!=32||groups!=3)return 1;
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
  id<MTLCommandBuffer>pending=nil,bad=[mode isEqual:@"unretained_CB"]?[q commandBufferWithUnretainedReferences]:[q commandBuffer];
  if([mode isEqual:@"second_unprepared"]){id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:3];[c setKernelBuffer:params[3] offset:0 atIndex:2];}
  if([mode isEqual:@"pending_source"]){pending=[q commandBuffer];id<MTLBlitCommandEncoder>p=[pending blitCommandEncoder];if(![scope adaptBlitEncoder:p error:&error])return 8;[p copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(0,1)destination:icb destinationIndex:1];[p endEncoding];}
  b=[bad blitCommandEncoder];NSUInteger beforeRefusal=scope.events.count;BOOL rejected=NO;NSString*reason=nil;Class badClass=object_getClass(b);
  if([mode isEqual:@"unretained_CB"]){rejected=![scope adaptBlitEncoder:b error:&error];reason=error.localizedDescription;if(object_getClass(b)!=badClass)return 8;}
  else{if(![scope adaptBlitEncoder:b error:&error])return 8;@try{
   if([mode isEqual:@"pending_source"])[b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(1,1)destination:icb destinationIndex:2];
   else [b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(0,2)destination:icb destinationIndex:[mode isEqual:@"overlap"]?1:2];
  }@catch(NSException*x){rejected=YES;reason=x.reason;}}
  BOOL noPartialEvent=scope.events.count==beforeRefusal;if(!rejected||!reason.length||!noPartialEvent)return 8;[b endEncoding];
  BOOL discardedUncommitted=bad.status==MTLCommandBufferStatusNotEnqueued&&(!pending||pending.status==MTLCommandBufferStatusNotEnqueued);if(!discardedUncommitted)return 8;
  bad=nil;pending=nil;id<MTLCommandBuffer>main=[q commandBuffer];
  id<MTLComputeCommandEncoder>e=[main computeCommandEncoder];
#if !KP_GPU_COPY_NATIVE
  if(![scope adaptComputeEncoder:e error:&error])return 9;
#endif
  for(unsigned k=0;k<slots;k++){[e useResource:outputs[k]usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e useResource:counters[k]usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e useResource:params[k]usage:MTLResourceUsageRead];}
  [e executeCommandsInBuffer:icb withRange:NSMakeRange(2,1)];[e endEncoding];
#if KP_GPU_COPY_NATIVE
  NSArray*copyEvents=@[];
#else
  NSArray*copyEvents=[scope.events subarrayWithRange:NSMakeRange(eventStart,scope.events.count-eventStart)];
#endif
  __weak id<MTLBuffer>weakSourceParameter=params[0];[params removeAllObjects];icb=nil;BOOL ownerAliveBeforeCommit=weakSourceParameter!=nil;if(!ownerAliveBeforeCommit)return 10;
  auto readback=[&]()->BOOL{id<MTLCommandBuffer>r=[q commandBuffer];id<MTLBlitCommandEncoder>bl=[r blitCommandEncoder];for(unsigned k=0;k<slots;k++){[bl copyFromBuffer:outputs[k] sourceOffset:0 toBuffer:hostOut[k] destinationOffset:0 size:10368];[bl copyFromBuffer:counters[k] sourceOffset:0 toBuffer:hostCount[k] destinationOffset:0 size:132];}[bl endEncoding];return done(r);};
  if(!readback())return 10;for(unsigned k=0;k<slots;k++){id<MTLBuffer>ho=hostOut[k],hc=hostCount[k];for(NSUInteger i=0;i<10368;i++)if(((uint8_t*)ho.contents)[i]!=0xa5)return 10;uint32_t c=99;memcpy(&c,(char*)hc.contents+64,4);if(c)return 10;}
  if(!done(main))return 11;if(!readback())return 12;
  NSMutableArray*names=[NSMutableArray array];for(unsigned k=0;k<slots;k++)for(NSString*kind in @[@"output",@"counter"]){id<MTLBuffer>h=[kind isEqual:@"output"]?hostOut[k]:hostCount[k];NSString*name=[NSString stringWithFormat:@"trial-%u-%u-%@.bin",t,k,kind];if(![[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:name]atomically:YES])return 13;[names addObject:name];}
  [runs addObject:@{@"trial":@(t),@"seeds":seedRows,@"files":names,@"refusal":reason,@"rejected":@(rejected),@"no_partial_copy_event":@(noPartialEvent),@"discarded_uncommitted":@(discardedUncommitted),@"executed_index":@2,@"command_status":@(main.status),@"before_commit_untouched":@YES,@"ICB_external_reference_released_before_commit":@YES,@"parameter_external_references_released_before_commit":@YES,@"source_parameter_alive_before_commit":@(ownerAliveBeforeCommit),@"copy_events":copyEvents}];
 }}
#if KP_GPU_COPY_NATIVE
 NSArray*scopeEvents=@[];
#else
 [scope restore];NSArray*scopeEvents=scope.events;
#endif
 emit(@{@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),@"local":@(local),@"groups":@(groups),@"width":@(width),@"slots":@(slots),@"recipe":@(recipe),@"node_specs":nodeRows,@"runs":runs,@"scope_restored":@(object_getClass(d)==before),@"scope_events":scopeEvents,@"native_reference":@NO,@"adapter_policy_refusals":@YES,@"system_modified":@NO,@"CPU_expected_answers_uploaded":@NO,@"intermediate_descriptor_CPU_readback":@NO,@"full_ICB_contract":@NO,@"performance_benchmark":@NO});return object_getClass(d)==before?0:14;
}}
