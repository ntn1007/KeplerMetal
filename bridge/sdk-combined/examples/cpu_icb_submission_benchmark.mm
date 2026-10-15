#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <cstring>
#include <time.h>
#include <cmath>

static uint64_t ns(clockid_t clock){timespec t{};if(clock_gettime(clock,&t))return 0;return uint64_t(t.tv_sec)*1000000000+t.tv_nsec;}
static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static void emit(id x){NSData*j=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}

int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3)return 1;NSString*libraryPath=@(argv[1]),*out=@(argv[2]);id<MTLDevice>d=nil;
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
 Class original=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 KPCPUICBScope*scope=[KPCPUICBScope installOnDevice:d queue:q libraryURL:[NSURL fileURLWithPath:libraryPath] expectedSHA256:@"913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd" error:&error];if(!scope)return 3;
 NSArray*functions=@[@"profile_integer",@"profile_fma",@"profile_shared"];
 unsigned locals[3]={32,33,64},groups[3]={3,3,2},seeds[3]={0x3311,0x7733,0xbb55};
 NSMutableArray*outputs=[NSMutableArray array],*counters=[NSMutableArray array],*params=[NSMutableArray array],*hostOut=[NSMutableArray array],*hostCount=[NSMutableArray array];
 for(unsigned k=0;k<3;k++){
  id<MTLBuffer>o=[d newBufferWithLength:10368 options:MTLResourceStorageModePrivate],c=[d newBufferWithLength:132 options:MTLResourceStorageModePrivate],p=[d newBufferWithLength:512 options:MTLResourceStorageModeShared],ho=[d newBufferWithLength:10368 options:MTLResourceStorageModeShared],hc=[d newBufferWithLength:132 options:MTLResourceStorageModeShared];if(!o||!c||!p||!ho||!hc)return 4;
  memset(p.contents,0xa5,512);uint32_t words[4]={seeds[k],groups[k],locals[k],640};memcpy(p.contents,words,16);
  [outputs addObject:o];[counters addObject:c];[params addObject:p];[hostOut addObject:ho];[hostCount addObject:hc];
 }
 auto resetOutputs=[&]()->BOOL{
  id<MTLCommandBuffer>u=[q commandBuffer];id<MTLBlitCommandEncoder>b=[u blitCommandEncoder];
  for(unsigned k=0;k<3;k++){id<MTLBuffer>ho=hostOut[k],hc=hostCount[k];memset(ho.contents,0xa5,10368);memset(hc.contents,0xa5,132);uint32_t zero=0;memcpy((char*)hc.contents+64,&zero,4);[b copyFromBuffer:ho sourceOffset:0 toBuffer:outputs[k]destinationOffset:0 size:10368];[b copyFromBuffer:hc sourceOffset:0 toBuffer:counters[k]destinationOffset:0 size:132];}
  [b endEncoding];return done(u);
 };
 if(!resetOutputs())return 5;
 MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;desc.maxKernelBufferBindCount=3;
 id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:3 options:MTLResourceStorageModeShared];if(!icb)return 6;
 for(unsigned k=0;k<3;k++){id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:k];[c setComputePipelineState:[scope pipelineForFunction:functions[k]]];[c setKernelBuffer:outputs[k]offset:64 atIndex:0];[c setKernelBuffer:counters[k]offset:64 atIndex:1];[c setKernelBuffer:params[k]offset:0 atIndex:2];[c concurrentDispatchThreadgroups:MTLSizeMake(groups[k],1,1)threadsPerThreadgroup:MTLSizeMake(locals[k],1,1)];}
 if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,3)error:&error])return 7;
 NSMutableArray*runs=[NSMutableArray array];const unsigned iterations=32;NSArray*modes=@[@"wait_each",@"submit_all",@"single_CB"];
 for(unsigned cycle=0;cycle<12;cycle++)for(unsigned order=0;order<3;order++){@autoreleasepool{
  NSString*mode=modes[(cycle+order)%3];BOOL single=[mode isEqual:@"single_CB"],waitEach=[mode isEqual:@"wait_each"],warmup=cycle<3;
  if(!resetOutputs())return 5;NSUInteger eventStart=scope.events.count;NSMutableArray*buffers=[NSMutableArray array];id<MTLCommandBuffer>batch=nil,last=nil;
  unsigned submits=0,waits=0,blits=0,computes=0,copies=0,dispatches=0;
  uint64_t wall0=ns(CLOCK_MONOTONIC),process0=ns(CLOCK_PROCESS_CPUTIME_ID),thread0=ns(CLOCK_THREAD_CPUTIME_ID);if(!wall0||!process0||!thread0)return 8;
  if(single){batch=[q commandBuffer];[buffers addObject:batch];}
  @try{for(unsigned i=0;i<iterations;i++){
   id<MTLCommandBuffer>p=single?batch:[q commandBuffer];if(!single)[buffers addObject:p];id<MTLBlitCommandEncoder>b=[p blitCommandEncoder];if(![scope adaptBlitEncoder:b error:&error])return 9;
   [b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(0,1)destination:icb destinationIndex:1];copies++;blits++;[b endEncoding];
   if(!single){[p commit];submits++;if(waitEach){[p waitUntilCompleted];waits++;if(p.status!=4)return 10;}}
   id<MTLCommandBuffer>m=single?batch:[q commandBuffer];if(!single)[buffers addObject:m];b=[m blitCommandEncoder];if(![scope adaptBlitEncoder:b error:&error])return 9;
   [b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(1,1)destination:icb destinationIndex:2];copies++;blits++;[b endEncoding];
   if(!single){[m commit];submits++;if(waitEach){[m waitUntilCompleted];waits++;if(m.status!=4)return 10;}}
   last=single?batch:[q commandBuffer];if(!single)[buffers addObject:last];id<MTLComputeCommandEncoder>e=[last computeCommandEncoder];if(![scope adaptComputeEncoder:e error:&error])return 9;
   for(unsigned k=0;k<3;k++){[e useResource:outputs[k]usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e useResource:counters[k]usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e useResource:params[k]usage:MTLResourceUsageRead];}
   [e executeCommandsInBuffer:icb withRange:NSMakeRange(2,1)];dispatches++;computes++;[e endEncoding];
   if(!single){[last commit];submits++;if(waitEach){[last waitUntilCompleted];waits++;if(last.status!=4)return 10;}}
  }
  if(single){[batch commit];submits++;}
  if(!waitEach){[last waitUntilCompleted];waits++;if(last.status!=4)return 10;}
  }@catch(NSException*x){fprintf(stderr,"%s\n",x.reason.UTF8String);return 11;}
  uint64_t thread1=ns(CLOCK_THREAD_CPUTIME_ID),process1=ns(CLOCK_PROCESS_CPUTIME_ID),wall1=ns(CLOCK_MONOTONIC);
  NSMutableArray*states=[NSMutableArray array];double first=INFINITY,end=0;BOOL timing=YES;
  for(id<MTLCommandBuffer>c in buffers){[states addObject:@(c.status)];if(c.status!=4)return 10;double a=c.GPUStartTime,b=c.GPUEndTime;if(!(a>0&&b>a&&std::isfinite(a)&&std::isfinite(b)))timing=NO;else{first=fmin(first,a);end=fmax(end,b);}}
  NSArray*events=[scope.events subarrayWithRange:NSMakeRange(eventStart,scope.events.count-eventStart)];
  id<MTLCommandBuffer>read=[q commandBuffer];id<MTLBlitCommandEncoder>r=[read blitCommandEncoder];for(unsigned k=0;k<3;k++){[r copyFromBuffer:outputs[k]sourceOffset:0 toBuffer:hostOut[k]destinationOffset:0 size:10368];[r copyFromBuffer:counters[k]sourceOffset:0 toBuffer:hostCount[k]destinationOffset:0 size:132];}[r endEncoding];if(!done(read))return 12;
  NSMutableArray*files=[NSMutableArray array];for(unsigned k=0;k<3;k++)for(NSString*kind in @[@"output",@"counter"]){id<MTLBuffer>h=[kind isEqual:@"output"]?hostOut[k]:hostCount[k];NSString*n=[NSString stringWithFormat:@"cycle-%u-%@-%u-%@.bin",cycle,mode,k,kind];if(![[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:n]atomically:YES])return 13;[files addObject:n];}
  [runs addObject:@{@"cycle":@(cycle),@"order":@(order),@"mode":mode,@"warmup":@(warmup),@"iterations":@(iterations),@"command_buffers":@(buffers.count),@"submissions":@(submits),@"explicit_completion_waits":@(waits),@"blit_encoders":@(blits),@"compute_encoders":@(computes),@"QMD_copies":@(copies),@"user_dispatches":@(dispatches),@"command_buffer_final_states":states,@"wall_ns":@(wall1-wall0),@"process_CPU_ns":@(process1-process0),@"thread_CPU_ns":@(thread1-thread0),@"GPU_span_ms":timing?@((end-first)*1000):(id)[NSNull null],@"GPU_span_includes_scheduling_gaps":@YES,@"files":files,@"events":events}];
 }}
 [scope restore];emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"runs":runs,@"source_function":@"profile_integer",@"source_local":@32,@"source_groups":@3,@"source_seed":@0x3311,@"scope_restored":@(object_getClass(d)==original),@"timed_region":@"encode/adapt/validate/submit and explicit completion waits, including current SDK tracing; excludes preparation, output reset/readback, file IO, statistics and autorelease-pool drain",@"cold_preparation_excluded":@YES,@"output_transfers_excluded":@YES,@"work_identical_between_modes":@YES,@"gated_waits":@NO,@"system_modified":@NO,@"new_driver_installed":@NO,@"CPU_expected_answers_uploaded":@NO,@"intermediate_descriptor_CPU_readback":@NO,@"full_ICB_contract":@NO,@"performance_benchmark":@YES});return 0;
}}
