#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>

#ifndef KP_COMBINED_NATIVE
#define KP_COMBINED_NATIVE 0
#endif

struct P { uint32_t seed, groups, local, max_n, scratch_words; };
static NSString *sha(NSData *data) {
 unsigned char bytes[32]; CC_SHA256(data.bytes, (CC_LONG)data.length, bytes);
 NSMutableString *s=[NSMutableString new]; for(unsigned char b:bytes)[s appendFormat:@"%02x",b]; return s;
}
static BOOL done(id<MTLCommandBuffer>c) { [c commit]; [c waitUntilCompleted]; return c.status==MTLCommandBufferStatusCompleted; }
static void emit(id x) { NSData*j=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil]; fwrite(j.bytes,1,j.length,stdout); puts(""); }

int main(int argc,char**argv) { @autoreleasepool {
 if(argc!=4)return 1;
 NSString *assets=@(argv[1]), *out=@(argv[2]), *mode=@(argv[3]);
 if(![@[@"prepare_bound",@"prepare_private",@"copy_bound",@"owner_bound",@"execute_owner_bound"] containsObject:mode])return 1;
 BOOL prepare=NO, negative=NO, completed=NO;
 BOOL cold=[mode isEqual:@"prepare_bound"]||[mode isEqual:@"prepare_private"], privateCase=[mode isEqual:@"prepare_private"];
 BOOL ownerCase=[mode isEqual:@"owner_bound"]||[mode isEqual:@"execute_owner_bound"];
 NSUInteger width=2, slots=6;
 id<MTLDevice>d=nil;
#if KP_COMBINED_NATIVE
 d=MTLCreateSystemDefaultDevice();
#else
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;
#endif
 if(!d)return 2;
 Class original=object_getClass(d); id<MTLCommandQueue>q=[d newCommandQueue]; NSError*error=nil;
 NSData *library=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"combined_shared.metallib"]];
 NSData *manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"cpu_icb_combined_shared_manifest.json"]];
 NSArray *names=@[@"shared_mix_s128",@"shared_mix_s1024",@"shared_mix_s4096"]; NSMutableDictionary*pipelines=[NSMutableDictionary new];
#if KP_COMBINED_NATIVE
 id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"combined_shared.metallib"]] error:&error]; if(!lib)return 3;
 for(NSString*n in names) {
  MTLComputePipelineDescriptor*desc=[MTLComputePipelineDescriptor new]; desc.computeFunction=[lib newFunctionWithName:n]; desc.supportIndirectCommandBuffers=YES;
  id<MTLComputePipelineState>p=[d newComputePipelineStateWithDescriptor:desc options:MTLPipelineOptionNone reflection:nil error:&error]; if(!p)return 3; pipelines[n]=p;
 }
#else
 KPCPUICBScope*scope=[KPCPUICBScope installOnDevice:d queue:q libraryData:library expectedSHA256:sha(library) manifestData:manifest expectedManifestSHA256:sha(manifest) error:&error];
 if(!scope){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;} for(NSString*n in names)pipelines[n]=[scope pipelineForFunction:n];
#endif
 const unsigned locals[3][6]={{32,33,128,256,512,1024},{512,1024,32,33,128,256},{128,256,512,1024,32,33}};
 const unsigned profiles[3][6]={{0,1,2,0,1,2},{2,0,1,2,0,1},{1,2,0,1,2,0}};
 const unsigned statics[3]={512,4096,16384};
 const NSUInteger bytes=8192*16+512; NSMutableArray*runs=[NSMutableArray new];
 for(unsigned t=0;t<3;t++) { @autoreleasepool {
  NSMutableArray*outputs=[NSMutableArray new], *outputHosts=[NSMutableArray new], *counters=[NSMutableArray new], *counterHosts=[NSMutableArray new], *params=[NSMutableArray new], *specs=[NSMutableArray new];
  for(unsigned k=0;k<slots;k++) {
   unsigned local=locals[t][k], groups=local<=33?3:local==128?5:local==256?2:1, count=local*groups, seed=0x765431+t*97+k*101;
   unsigned staticBytes=statics[profiles[t][k]],dynamic=(t==0||k==1)?49152-staticBytes:1024*(k+1);if(k==1)dynamic=4096;if(k==3)dynamic=1024;if(k==5)dynamic=49152-staticBytes;
   P p={seed,groups,local,count,dynamic/4};
   id<MTLBuffer>o=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate], h=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];
   id<MTLBuffer>c=[d newBufferWithLength:208 options:MTLResourceStorageModePrivate], ch=[d newBufferWithLength:208 options:MTLResourceStorageModeShared], parameter=[d newBufferWithLength:2048 options:MTLResourceStorageModeShared];
   if(!o||!h||!c||!ch||!parameter)return 4;
   memset(h.contents,0xa5,h.length); memset(ch.contents,0xa5,ch.length); memset((char*)ch.contents+128,0,4);
   memset(parameter.contents,0xa5,parameter.length); memcpy((char*)parameter.contents+1024,&p,sizeof(p));
   [outputs addObject:o]; [outputHosts addObject:h]; [counters addObject:c]; [counterHosts addObject:ch]; [params addObject:parameter];
   [specs addObject:@{@"function":names[profiles[t][k]], @"local":@(local), @"groups":@(groups), @"count":@(count), @"seed":@(seed), @"static_bytes":@(staticBytes), @"dynamic_bytes":@(dynamic)}];
  }
  id<MTLCommandBuffer>init=[q commandBuffer]; id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];
  for(unsigned k=0;k<slots;k++) {
   [b copyFromBuffer:outputHosts[k] sourceOffset:0 toBuffer:outputs[k] destinationOffset:0 size:bytes];
   [b copyFromBuffer:counterHosts[k] sourceOffset:0 toBuffer:counters[k] destinationOffset:0 size:208];
  }
  [b endEncoding]; if(!done(init))return 5;
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new]; desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;
  desc.inheritBuffers=NO; desc.inheritPipelineState=NO; desc.maxKernelBufferBindCount=3;
  id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:slots options:MTLResourceStorageModeShared]; if(!icb)return 6;
  for(unsigned k=0;k<slots;k++) {
   NSDictionary*s=specs[k]; id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:k];
   [c setComputePipelineState:pipelines[s[@"function"]]]; [c setKernelBuffer:outputs[k] offset:128 atIndex:0];
   [c setKernelBuffer:counters[k] offset:128 atIndex:1]; [c setKernelBuffer:params[k] offset:1024 atIndex:2];
   if([s[@"dynamic_bytes"]unsignedIntegerValue])[c setThreadgroupMemoryLength:[s[@"dynamic_bytes"]unsignedIntegerValue] atIndex:0];
   [c concurrentDispatchThreadgroups:MTLSizeMake([s[@"groups"]unsignedIntegerValue],1,1) threadsPerThreadgroup:MTLSizeMake([s[@"local"]unsignedIntegerValue],1,1)];
  }
  if(!cold&&! [scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots) error:&error])return 7;
  NSArray*preparation=scope.events; NSDictionary*firstCopy=@{};
  if(ownerCase) {
   id<MTLCommandBuffer>producer=[q commandBuffer]; id<MTLBlitCommandEncoder>bl=[producer blitCommandEncoder];
   if(![scope adaptBlitEncoder:bl error:&error])return 8;
   [bl copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(0,1) destination:icb destinationIndex:1];
   firstCopy=scope.events.lastObject; [bl endEncoding]; if(!done(producer))return 8;
   [icb resetWithRange:NSMakeRange(0,1)];
  }
  NSUInteger eventStart=scope.events.count, probeIndex=cold?5:ownerCase?1:3;
  uint32_t originalWords=[specs[probeIndex][@"dynamic_bytes"]unsignedIntValue]/4, badWords=originalWords+4;
  id<MTLBuffer>parameter=params[probeIndex], privateParameter=nil;
  if(privateCase) {
   privateParameter=[d newBufferWithLength:parameter.length options:MTLResourceStorageModePrivate]; if(!privateParameter)return 8;
   id<MTLCommandBuffer>upload=[q commandBuffer]; id<MTLBlitCommandEncoder>bl=[upload blitCommandEncoder];
   [bl copyFromBuffer:parameter sourceOffset:0 toBuffer:privateParameter destinationOffset:0 size:parameter.length]; [bl endEncoding]; if(!done(upload))return 8;
   [[icb indirectComputeCommandAtIndex:probeIndex]setKernelBuffer:privateParameter offset:1024 atIndex:2];
  } else memcpy((char*)parameter.contents+1024+16,&badWords,4);
  BOOL refused=NO; NSString*reason=@"";
  if(cold) {
   refused=! [scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots) error:&error]; reason=error.localizedDescription?:@"";
  } else {
   id<MTLCommandBuffer>bad=[q commandBuffer];
   if([mode isEqual:@"execute_owner_bound"]) {
    id<MTLComputeCommandEncoder>ce=[bad computeCommandEncoder]; if(![scope adaptComputeEncoder:ce error:&error])return 9;
    @try { [ce executeCommandsInBuffer:icb withRange:NSMakeRange(1,1)]; } @catch(NSException*x) { refused=YES; reason=x.reason?:@""; }
    [ce endEncoding];
   } else {
    id<MTLBlitCommandEncoder>bl=[bad blitCommandEncoder]; if(![scope adaptBlitEncoder:bl error:&error])return 9;
    @try { [bl copyIndirectCommandBuffer:icb sourceRange:ownerCase?NSMakeRange(1,1):NSMakeRange(0,2) destination:icb destinationIndex:2]; }
    @catch(NSException*x) { refused=YES; reason=x.reason?:@""; }
    [bl endEncoding];
   }
   if(bad.status!=MTLCommandBufferStatusNotEnqueued)return 9;
  }
  BOOL unchanged=scope.events.count==eventStart; if(!refused||!unchanged)return 9;
  memcpy((char*)parameter.contents+1024+16,&originalWords,4);
  if(privateCase)[[icb indirectComputeCommandAtIndex:probeIndex]setKernelBuffer:parameter offset:1024 atIndex:2];
  NSUInteger selected=cold?0:ownerCase?1:2, activeOutput=ownerCase?0:selected;
  id<MTLCommandBuffer>main=[q commandBuffer]; id<MTLComputeCommandEncoder>e=[main computeCommandEncoder];
  if(![scope adaptComputeEncoder:e error:&error])return 9;
  for(id<MTLBuffer>o in outputs)[e useResource:o usage:MTLResourceUsageRead|MTLResourceUsageWrite];
  for(id<MTLBuffer>c in counters)[e useResource:c usage:MTLResourceUsageRead|MTLResourceUsageWrite];
  for(id<MTLBuffer>p in params)[e useResource:p usage:MTLResourceUsageRead];
  [e executeCommandsInBuffer:icb withRange:NSMakeRange(selected,1)]; [e endEncoding];
  NSArray*events=[scope.events subarrayWithRange:NSMakeRange(eventStart,scope.events.count-eventStart)];
  icb=nil; [params removeAllObjects];
  auto readback=[&]()->BOOL {
   id<MTLCommandBuffer>r=[q commandBuffer]; id<MTLBlitCommandEncoder>bl=[r blitCommandEncoder];
   for(unsigned k=0;k<slots;k++) {
    [bl copyFromBuffer:outputs[k] sourceOffset:0 toBuffer:outputHosts[k] destinationOffset:0 size:bytes];
    [bl copyFromBuffer:counters[k] sourceOffset:0 toBuffer:counterHosts[k] destinationOffset:0 size:208];
   }
   [bl endEncoding]; return done(r);
  };
  if(!readback())return 10;
  for(id<MTLBuffer>h in outputHosts)for(unsigned i=0;i<bytes;i++)if(((uint8_t*)h.contents)[i]!=0xa5)return 10;
  for(id<MTLBuffer>h in counterHosts){uint32_t c=99;memcpy(&c,(char*)h.contents+128,4);if(c)return 10;}
  if(!prepare&&!done(main))return 11; if(!readback())return 12;
  NSMutableArray*files=[NSMutableArray new], *countFiles=[NSMutableArray new];
  for(unsigned k=0;k<slots;k++) {
   id<MTLBuffer>h=outputHosts[k], ch=counterHosts[k];
   NSString*n=[NSString stringWithFormat:@"trial-%u-slot-%u.bin",t,k], *cn=[NSString stringWithFormat:@"trial-%u-counter-%u.bin",t,k];
   if(![[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:n]atomically:YES]||![[NSData dataWithBytes:ch.contents length:ch.length]writeToFile:[out stringByAppendingPathComponent:cn]atomically:YES])return 13;
   [files addObject:n]; [countFiles addObject:cn];
  }
  [runs addObject:@{@"trial":@(t), @"node_specs":specs, @"outputs":files, @"counter_files":countFiles, @"copy_events":events, @"preparation_events":preparation,
   @"committed":@YES, @"command_status":@(main.status), @"before_commit_untouched":@YES,
   @"refused":@(refused), @"refusal_reason":reason, @"events_unchanged_at_refusal":@(unchanged), @"bad_command_buffer_committed":@NO, @"probe_index":@(probeIndex), @"selected_index":@(selected), @"active_output_index":@(activeOutput), @"private_parameter_rejected":@(privateCase), @"first_copy_completed":@(ownerCase), @"original_source_reset":@(ownerCase), @"first_copy_evidence":firstCopy,
   @"source_reset_after_completed_producer":@(completed), @"ICB_and_parameter_external_refs_released_before_commit":@YES}];
 }}
#if !KP_COMBINED_NATIVE
 [scope restore];
#endif
 emit(@{@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),@"native_reference":@(KP_COMBINED_NATIVE!=0),@"width":@(width),@"slots":@(slots),@"runs":runs,
  @"scope_restored":@(object_getClass(d)==original),@"system_modified":@NO,@"CPU_expected_answers_uploaded":@NO,@"intermediate_descriptor_CPU_readback":@NO,@"performance_benchmark":@NO,@"full_ICB_contract":@NO});
 return 0;
}}
