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
 if(![@[@"prepare",@"chain",@"range",@"chain_completed",@"range_completed",@"no_second"] containsObject:mode])return 1;
 BOOL prepare=[mode isEqual:@"prepare"], negative=[mode isEqual:@"no_second"];
 BOOL completed=[mode hasSuffix:@"_completed"], wide=[mode hasPrefix:@"range"];
 NSUInteger width=wide?2:1, slots=width*3;
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
   unsigned staticBytes=statics[profiles[t][k]], dynamicBytes=(t==0||k==1)?49152-staticBytes:1024u*(k+1u);
   P p={seed,groups,local,count,dynamicBytes/4};
   id<MTLBuffer>o=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate], h=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];
   id<MTLBuffer>c=[d newBufferWithLength:208 options:MTLResourceStorageModePrivate], ch=[d newBufferWithLength:208 options:MTLResourceStorageModeShared], parameter=[d newBufferWithLength:2048 options:MTLResourceStorageModeShared];
   if(!o||!h||!c||!ch||!parameter)return 4;
   memset(h.contents,0xa5,h.length); memset(ch.contents,0xa5,ch.length); memset((char*)ch.contents+128,0,4);
   memset(parameter.contents,0xa5,parameter.length); memcpy((char*)parameter.contents+1024,&p,sizeof(p));
   [outputs addObject:o]; [outputHosts addObject:h]; [counters addObject:c]; [counterHosts addObject:ch]; [params addObject:parameter];
   [specs addObject:@{@"function":names[profiles[t][k]], @"local":@(local), @"groups":@(groups), @"count":@(count), @"seed":@(seed), @"static_bytes":@(staticBytes), @"dynamic_bytes":@(dynamicBytes)}];
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
#if !KP_COMBINED_NATIVE
  if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots) error:&error]){fprintf(stderr,"%s\n",error.description.UTF8String);return 7;}
  NSArray*preparation=scope.events; NSUInteger eventStart=preparation.count;
#endif
  id<MTLCommandBuffer>main=[q commandBuffer], producer=completed?[q commandBuffer]:main; b=[producer blitCommandEncoder];
#if !KP_COMBINED_NATIVE
  if(![scope adaptBlitEncoder:b error:&error])return 8;
#endif
  [b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(0,width) destination:icb destinationIndex:width];
  if(completed) {
   [b endEncoding]; if(!done(producer))return 8; [icb resetWithRange:NSMakeRange(0,width)]; b=[main blitCommandEncoder];
#if !KP_COMBINED_NATIVE
   if(![scope adaptBlitEncoder:b error:&error])return 8;
#endif
  }
  if(!negative)[b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(width,width) destination:icb destinationIndex:width*2];
  [b endEncoding]; id<MTLComputeCommandEncoder>e=[main computeCommandEncoder];
#if !KP_COMBINED_NATIVE
  if(![scope adaptComputeEncoder:e error:&error])return 9;
#endif
  for(id<MTLBuffer>o in outputs)[e useResource:o usage:MTLResourceUsageRead|MTLResourceUsageWrite];
  for(id<MTLBuffer>c in counters)[e useResource:c usage:MTLResourceUsageRead|MTLResourceUsageWrite];
  for(id<MTLBuffer>p in params)[e useResource:p usage:MTLResourceUsageRead];
  [e executeCommandsInBuffer:icb withRange:NSMakeRange(width*2,width)]; [e endEncoding];
#if KP_COMBINED_NATIVE
  NSArray*events=@[], *preparation=@[];
#else
  NSArray*events=[scope.events subarrayWithRange:NSMakeRange(eventStart,scope.events.count-eventStart)];
#endif
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
   @"committed":@(!prepare), @"command_status":@(main.status), @"before_commit_untouched":@YES,
   @"source_reset_after_completed_producer":@(completed), @"ICB_and_parameter_external_refs_released_before_commit":@YES}];
 }}
#if !KP_COMBINED_NATIVE
 [scope restore];
#endif
 emit(@{@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),@"native_reference":@(KP_COMBINED_NATIVE!=0),@"width":@(width),@"slots":@(slots),@"runs":runs,
  @"scope_restored":@(object_getClass(d)==original),@"system_modified":@NO,@"CPU_expected_answers_uploaded":@NO,@"intermediate_descriptor_CPU_readback":@NO,@"performance_benchmark":@NO,@"full_ICB_contract":@NO});
 return 0;
}}
