// Own-process prototype: native GPU QMD copy followed by a resident launch.
// Both descriptors are initialized/valid; omission selects the old B command.
#import "KeplerCPUICB.h"
#import "KeplerNativeCommands.h"
#import <objc/runtime.h>
#include <cstring>

static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static void emit(id x){NSData*j=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6)return 1;NSString*libraryPath=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);NSUInteger local=strtoul(argv[4],nullptr,10),groups=strtoul(argv[5],nullptr,10);BOOL prep=[mode isEqual:@"prepare"],copy=[mode isEqual:@"copy"],noCopy=[mode isEqual:@"no_copy"];
 if((!prep&&!copy&&!noCopy)||(local!=32&&local!=33&&local!=128)||(groups!=3&&groups!=5)||local*groups>640)return 1;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;Class before=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 KPCPUICBScope*scope=[KPCPUICBScope installOnDevice:d queue:q libraryURL:[NSURL fileURLWithPath:libraryPath] expectedSHA256:@"913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd" error:&error];if(!scope){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}id<MTLComputePipelineState>pipeline=[scope pipelineForFunction:@"profile_integer"];if(!pipeline)return 3;
 NSMutableArray*runs=[NSMutableArray array];
 for(unsigned t=0;t<3;t++){@autoreleasepool{
  NSMutableArray*outputs=[NSMutableArray array],*counters=[NSMutableArray array],*params=[NSMutableArray array],*hostOut=[NSMutableArray array],*hostCount=[NSMutableArray array];
  uint32_t seeds[2]={0x3311u+t*97u,0x7733u+t*101u};
  for(unsigned k=0;k<2;k++){
   id<MTLBuffer>o=[d newBufferWithLength:10368 options:MTLResourceStorageModePrivate],c=[d newBufferWithLength:132 options:MTLResourceStorageModePrivate],p=[d newBufferWithLength:512 options:MTLResourceStorageModeShared],ho=[d newBufferWithLength:10368 options:MTLResourceStorageModeShared],hc=[d newBufferWithLength:132 options:MTLResourceStorageModeShared];if(!o||!c||!p||!ho||!hc)return 4;
   memset(ho.contents,0xa5,10368);memset(hc.contents,0xa5,132);uint32_t zero=0;memcpy((char*)hc.contents+64,&zero,4);memset(p.contents,0xa5,512);uint32_t words[4]={seeds[k],(uint32_t)groups,(uint32_t)local,640};memcpy(p.contents,words,16);
   [outputs addObject:o];[counters addObject:c];[params addObject:p];[hostOut addObject:ho];[hostCount addObject:hc];
  }
  id<MTLCommandBuffer>upload=[q commandBuffer];id<MTLBlitCommandEncoder>b=[upload blitCommandEncoder];for(unsigned k=0;k<2;k++){[b copyFromBuffer:hostOut[k] sourceOffset:0 toBuffer:outputs[k] destinationOffset:0 size:10368];[b copyFromBuffer:hostCount[k] sourceOffset:0 toBuffer:counters[k] destinationOffset:0 size:132];}[b endEncoding];if(!done(upload))return 5;
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;desc.maxKernelBufferBindCount=3;
  id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:2 options:MTLResourceStorageModeShared];if(!icb)return 6;
  for(unsigned k=0;k<2;k++){id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:k];[c setComputePipelineState:pipeline];[c setKernelBuffer:outputs[k] offset:64 atIndex:0];[c setKernelBuffer:counters[k] offset:64 atIndex:1];[c setKernelBuffer:params[k] offset:0 atIndex:2];[c concurrentDispatchThreadgroups:MTLSizeMake(groups,1,1)threadsPerThreadgroup:MTLSizeMake(local,1,1)];}
  // Materialize validated native records through the existing CPU ICB path,
  // while leaving its user command buffer uncommitted.
  id<MTLCommandBuffer>uncommitted=[q commandBuffer];id<MTLComputeCommandEncoder>e=[uncommitted computeCommandEncoder];if(![scope adaptComputeEncoder:e error:&error])return 7;[e executeCommandsInBuffer:icb withRange:NSMakeRange(0,2)];[e endEncoding];
  KPRecordedNativeCompute*a=[(id)[icb indirectComputeCommandAtIndex:0]valueForKey:@"record"],*destination=[(id)[icb indirectComputeCommandAtIndex:1]valueForKey:@"record"];if(![a isKindOfClass:KPRecordedNativeCompute.class]||![destination isKindOfClass:KPRecordedNativeCompute.class])return 7;
  id<MTLCommandBuffer>initialize=[q commandBuffer];NSDictionary*initA=nil,*initB=nil;if(![a initializeResidentDescriptorInCommandBuffer:initialize evidence:&initA error:&error]||![destination initializeResidentDescriptorInCommandBuffer:initialize evidence:&initB error:&error]||!done(initialize))return 8;
  id<MTLCommandBuffer>main=[q commandBuffer];BOOL encodedCopy=copy||prep;if(encodedCopy){b=[main blitCommandEncoder];[b copyFromBuffer:a.descriptor sourceOffset:0 toBuffer:destination.descriptor destinationOffset:0 size:256];[b endEncoding];}
  e=[main computeCommandEncoder];NSDictionary*launch=nil;if(![destination encodeResidentDescriptorWithOwners:@[destination,a] encoder:e suppress:NO evidence:&launch error:&error]){fprintf(stderr,"%s\n",error.description.UTF8String);return 9;}[e endEncoding];
  auto readback=[&]()->BOOL{id<MTLCommandBuffer>r=[q commandBuffer];id<MTLBlitCommandEncoder>bl=[r blitCommandEncoder];for(unsigned k=0;k<2;k++){[bl copyFromBuffer:outputs[k] sourceOffset:0 toBuffer:hostOut[k] destinationOffset:0 size:10368];[bl copyFromBuffer:counters[k] sourceOffset:0 toBuffer:hostCount[k] destinationOffset:0 size:132];}[bl endEncoding];return done(r);};
  if(!readback())return 10;for(unsigned k=0;k<2;k++){id<MTLBuffer>ho=hostOut[k],hc=hostCount[k];for(NSUInteger i=0;i<10368;i++)if(((uint8_t*)ho.contents)[i]!=0xa5)return 10;uint32_t c=99;memcpy(&c,(char*)hc.contents+64,4);if(c)return 10;}
  if(!prep&&!done(main))return 11;if(!readback())return 12;
  NSMutableArray*names=[NSMutableArray array];for(unsigned k=0;k<2;k++)for(NSString*kind in @[@"output",@"counter"]){id<MTLBuffer>h=[kind isEqual:@"output"]?hostOut[k]:hostCount[k];NSString*name=[NSString stringWithFormat:@"trial-%u-%u-%@.bin",t,k,kind];if(![[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:name]atomically:YES])return 13;[names addObject:name];}
  [runs addObject:@{@"trial":@(t),@"seeds":@[@(seeds[0]),@(seeds[1])],@"local":@(local),@"groups":@(groups),@"files":names,@"copy_encoded":@(encodedCopy),@"copy_executed":@(copy),@"committed":@(!prep),@"command_status":@(main.status),@"before_commit_untouched":@YES,@"uncommitted_materialization_status":@(uncommitted.status),@"initialization":@[initA,initB],@"resident_launch":launch,@"source_QMD_address":@(a.descriptor.gpuAddress),@"destination_QMD_address":@(destination.descriptor.gpuAddress)}];
 }}[scope restore];emit(@{@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),@"local":@(local),@"groups":@(groups),@"runs":runs,@"scope_restored":@(object_getClass(d)==before),@"scope_events":scope.events,@"system_modified":@NO,@"CPU_expected_answers_uploaded":@NO,@"intermediate_descriptor_CPU_readback":@NO,@"full_ICB_contract":@NO,@"performance_benchmark":@NO});return object_getClass(d)==before?0:14;
}}
