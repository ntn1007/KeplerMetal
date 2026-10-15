#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#ifndef KP_SELECT_NATIVE
#define KP_SELECT_NATIVE 0
#endif
struct P{uint32_t seed,groups,local,max_n,scratch_words;};
static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char b:h)[s appendFormat:@"%02x",b];return s;}
static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static void emit(id x){NSData*d=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}
static id<MTLLibrary>load(id<MTLDevice>d,NSString*p,NSError**e){NSData*x=[NSData dataWithContentsOfFile:p];dispatch_data_t v=dispatch_data_create(x.bytes,x.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)x.length;});return[d newLibraryWithData:v error:e];}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
 if(![@[@"refusals"]containsObject:mode])return 1;
 BOOL prepare=NO,split=NO,completed=NO,copy=NO,producer=YES,selector=YES;
 NSUInteger rows=[mode isEqual:@"range"]?2:1,candidates=3,slots=candidates+rows*(copy?2:1);
 id<MTLDevice>d=nil;
#if KP_SELECT_NATIVE
 d=MTLCreateSystemDefaultDevice();
#else
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;
#endif
 if(!d)return 2;Class original=object_getClass(d);NSError*error=nil;id<MTLCommandQueue>q=[d newCommandQueue];
 NSArray*names=@[@"shared_mix_s128",@"shared_mix_s1024",@"shared_mix_s4096"];NSMutableDictionary*pipelines=[NSMutableDictionary new];
 NSData*libdata=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"combined_shared.metallib"]],*manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"cpu_icb_combined_shared_manifest.json"]],*seldata=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"gpu_command_selector.metallib"]],*geodata=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"gpu_command_geometry.metallib"]];
#if KP_SELECT_NATIVE
 id<MTLLibrary>library=load(d,[assets stringByAppendingPathComponent:@"combined_shared.metallib"],&error),selLib=load(d,[assets stringByAppendingPathComponent:@"gpu_command_geometry.metallib"],&error);if(!library||!selLib)return 3;
 for(NSString*n in names){MTLComputePipelineDescriptor*x=[MTLComputePipelineDescriptor new];x.computeFunction=[library newFunctionWithName:n];x.supportIndirectCommandBuffers=YES;id<MTLComputePipelineState>p=[d newComputePipelineStateWithDescriptor:x options:MTLPipelineOptionNone reflection:nil error:&error];if(!p)return 3;pipelines[n]=p;}
 id<MTLFunction>selectorFunction=[selLib newFunctionWithName:@"generate_grid_prefix_from_gpu"];
 id<MTLComputePipelineState>producerPSO=[d newComputePipelineStateWithFunction:[selLib newFunctionWithName:@"produce_command_choices"]error:&error],selectorPSO=[d newComputePipelineStateWithFunction:selectorFunction error:&error];if(!producerPSO||!selectorPSO)return 3;
#else
 KPCPUICBScope*scope=[KPCPUICBScope installOnDevice:d queue:q libraryData:libdata expectedSHA256:sha(libdata)manifestData:manifest expectedManifestSHA256:sha(manifest)error:&error];if(!scope)return 3;
 if(![scope enableGPUCommandSelectionWithLibraryData:seldata expectedSHA256:@"b6d3f29fc4f85dd020f96fff3fc5f2586548aad483ea2649172b56545a9e581c" error:&error]){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}if(![scope enableGPUCommandGeometryWithLibraryData:geodata expectedSHA256:sha(geodata)error:&error]){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}for(NSString*n in names)pipelines[n]=[scope pipelineForFunction:n];
#endif
 const unsigned statics[3]={512,4096,16384},locals[3][6]={{32,33,128,256,512,1024},{512,1024,256,32,33,128},{128,256,32,1024,512,33}};
 NSMutableArray*runs=[NSMutableArray new];
 for(unsigned t=0;t<3;t++){@autoreleasepool{
  const NSUInteger bytes=8192*16+512;uint32_t nonce=0x9e37+31*t;NSMutableArray*refusals=[NSMutableArray new];
  NSMutableArray*outputs=[NSMutableArray new],*hosts=[NSMutableArray new],*counters=[NSMutableArray new],*counterHosts=[NSMutableArray new],*params=[NSMutableArray new],*specs=[NSMutableArray new];
  for(unsigned k=0;k<slots;k++){unsigned index=(k+t)%3,l=locals[t][k],g=k<3?(l==1024?4:7):3,sb=statics[index],db=k<3?49152-sb:1024*(k+1),seed=0x765431+t*97+k*101;P p={seed,g,l,g*l,db/4};
   id<MTLBuffer>o=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate],h=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared],c=[d newBufferWithLength:208 options:MTLResourceStorageModePrivate],ch=[d newBufferWithLength:208 options:MTLResourceStorageModeShared],pb=[d newBufferWithLength:2048 options:MTLResourceStorageModeShared];if(!o||!h||!c||!ch||!pb)return 4;
   memset(h.contents,0xa5,h.length);memset(ch.contents,0xa5,ch.length);memset((char*)ch.contents+128,0,4);memset(pb.contents,0xa5,pb.length);memcpy((char*)pb.contents+1024,&p,sizeof(p));[outputs addObject:o];[hosts addObject:h];[counters addObject:c];[counterHosts addObject:ch];[params addObject:pb];
   [specs addObject:@{@"function":names[index],@"local":@(l),@"groups":@(g),@"count":@(l*g),@"seed":@(seed),@"static_bytes":@(sb),@"dynamic_bytes":@(db)}];
  }
  id<MTLBuffer>input=[d newBufferWithLength:192+rows*128 options:MTLResourceStorageModePrivate],inputHost=[d newBufferWithLength:input.length options:MTLResourceStorageModeShared],inputRead=[d newBufferWithLength:input.length options:MTLResourceStorageModeShared];if(!input||!inputHost||!inputRead)return 4;memset(inputHost.contents,0xa5,inputHost.length);
  for(unsigned row=0;row<rows;row++)for(unsigned i=0;i<32;i++){uint32_t x=17*i+t*3+row*11+(i==31?(t==2?2:t+1):0);memcpy((char*)inputHost.contents+128+row*128+i*4,&x,4);}
  id<MTLCommandBuffer>init=[q commandBuffer];id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];for(unsigned k=0;k<slots;k++){[b copyFromBuffer:hosts[k]sourceOffset:0 toBuffer:outputs[k]destinationOffset:0 size:bytes];[b copyFromBuffer:counterHosts[k]sourceOffset:0 toBuffer:counters[k]destinationOffset:0 size:208];}[b copyFromBuffer:inputHost sourceOffset:0 toBuffer:input destinationOffset:0 size:input.length];[b endEncoding];if(!done(init))return 5;
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=3;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:slots options:MTLResourceStorageModeShared];if(!icb)return 6;
  for(unsigned k=0;k<slots;k++){NSDictionary*s=specs[k];id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:k];[c setComputePipelineState:pipelines[s[@"function"]]];[c setKernelBuffer:outputs[k]offset:128 atIndex:0];[c setKernelBuffer:counters[k]offset:128 atIndex:1];[c setKernelBuffer:params[k]offset:1024 atIndex:2];[c setThreadgroupMemoryLength:[s[@"dynamic_bytes"]unsignedIntegerValue]atIndex:0];[c concurrentDispatchThreadgroups:MTLSizeMake([s[@"groups"]unsignedIntegerValue],1,1)threadsPerThreadgroup:MTLSizeMake([s[@"local"]unsignedIntegerValue],1,1)];}
  id<MTLBuffer>choices=nil,counts=nil,geometry=nil;
#if KP_SELECT_NATIVE
  geometry=[d newBufferWithLength:128+rows*16 options:MTLResourceStorageModePrivate];id<MTLBuffer>limits=[d newBufferWithLength:48 options:MTLResourceStorageModeShared];memset(limits.contents,0,limits.length);for(unsigned k=0;k<3;k++){uint32_t v[4]={[specs[k][@"groups"]unsignedIntValue],[specs[k][@"local"]unsignedIntValue],0,0};memcpy((char*)limits.contents+k*16,v,16);}choices=[d newBufferWithLength:128+rows*16 options:MTLResourceStorageModePrivate];counts=[d newBufferWithLength:128+rows*8 options:MTLResourceStorageModePrivate];init=[q commandBuffer];b=[init blitCommandEncoder];[b fillBuffer:geometry range:NSMakeRange(0,geometry.length)value:0xa5];[b fillBuffer:geometry range:NSMakeRange(64,rows*16)value:0];[b fillBuffer:choices range:NSMakeRange(0,choices.length)value:0xa5];[b fillBuffer:choices range:NSMakeRange(64,rows*16)value:0];[b fillBuffer:counts range:NSMakeRange(0,counts.length)value:0xa5];[b fillBuffer:counts range:NSMakeRange(64,rows*8)value:0];[b endEncoding];if(!done(init))return 7;
  id<MTLArgumentEncoder>argumentEncoder=[selectorFunction newArgumentEncoderWithBufferIndex:0];id<MTLBuffer>argument=[d newBufferWithLength:argumentEncoder.encodedLength options:MTLResourceStorageModeShared];[argumentEncoder setArgumentBuffer:argument offset:0];[argumentEncoder setIndirectCommandBuffer:icb atIndex:0];
  uint32_t configWords[4]={nonce,3,0,0};id<MTLBuffer>producerConfig=[d newBufferWithLength:256 options:MTLResourceStorageModeShared];memcpy(producerConfig.contents,configWords,16);NSMutableArray*selectorConfigs=[NSMutableArray new];for(unsigned row=0;row<rows;row++){configWords[2]=row;configWords[3]=(uint32_t)(candidates+row);id<MTLBuffer>p=[d newBufferWithLength:256 options:MTLResourceStorageModeShared];memcpy(p.contents,configWords,16);[selectorConfigs addObject:p];}
#else
  id<MTLIndirectComputeCommand>boundCommand=[icb indirectComputeCommandAtIndex:0];
  [boundCommand concurrentDispatchThreadgroups:MTLSizeMake(8,1,1)threadsPerThreadgroup:MTLSizeMake([specs[0][@"local"]unsignedIntegerValue],1,1)];
  error=nil;NSUInteger boundEvents=scope.events.count;if([scope newGPUCommandGeometryFromBuffer:icb sourceRange:NSMakeRange(0,3)destination:icb destinationRange:NSMakeRange(3,1)input:input inputOffset:128 nonce:nonce error:&error]||!error||scope.events.count!=boundEvents)return 47;
  [refusals addObject:@{@"case":@"eight_groups_refused",@"refused":@YES,@"reason":error.localizedDescription,@"events_unchanged":@YES}];
  [boundCommand concurrentDispatchThreadgroups:MTLSizeMake([specs[0][@"groups"]unsignedIntegerValue],1,1)threadsPerThreadgroup:MTLSizeMake([specs[0][@"local"]unsignedIntegerValue],1,1)];
  if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots)error:&error])return 7;
  NSUInteger preflightEvents=scope.events.count;
  for(NSString*test in @[@"wrong_selector_hash",@"changed_selector_bytes",@"wrong_geometry_hash",@"changed_geometry_bytes",@"zero_candidates",@"overlap",@"shared_input",@"short_input"]) {
   error=nil;BOOL refused=NO;
   if([test isEqual:@"wrong_selector_hash"])refused=![scope enableGPUCommandSelectionWithLibraryData:seldata expectedSHA256:@"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" error:&error];
   else if([test isEqual:@"changed_selector_bytes"]){NSMutableData*bad=[seldata mutableCopy];((uint8_t*)bad.mutableBytes)[0]^=1;refused=![scope enableGPUCommandSelectionWithLibraryData:bad expectedSHA256:sha(seldata)error:&error];}
   else if([test isEqual:@"wrong_geometry_hash"])refused=![scope enableGPUCommandGeometryWithLibraryData:geodata expectedSHA256:@"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" error:&error];
   else if([test isEqual:@"changed_geometry_bytes"]){NSMutableData*bad=[geodata mutableCopy];((uint8_t*)bad.mutableBytes)[0]^=1;refused=![scope enableGPUCommandGeometryWithLibraryData:bad expectedSHA256:sha(geodata)error:&error];}
   else{NSRange sr=NSMakeRange(0,3),dr=NSMakeRange(3,1);id<MTLBuffer>testInput=input;NSUInteger offset=128;if([test isEqual:@"zero_candidates"])sr.length=0;if([test isEqual:@"overlap"])dr.location=1;if([test isEqual:@"shared_input"])testInput=inputHost;if([test isEqual:@"short_input"]){testInput=[d newBufferWithLength:32 options:MTLResourceStorageModePrivate];offset=0;}
    refused=![scope newGPUCommandGeometryFromBuffer:icb sourceRange:sr destination:icb destinationRange:dr input:testInput inputOffset:offset nonce:nonce error:&error];}
   if(!refused||!error||scope.events.count!=preflightEvents)return 41;[refusals addObject:@{@"case":test,@"refused":@YES,@"reason":error.localizedDescription,@"events_unchanged":@YES}];
  }
  KPGPUCommandSelection*stale=[scope newGPUCommandGeometryFromBuffer:icb sourceRange:NSMakeRange(0,3)destination:icb destinationRange:NSMakeRange(3,1)input:input inputOffset:128 nonce:nonce error:&error];if(!stale)return 48;
  id<MTLIndirectComputeCommand>changed=[icb indirectComputeCommandAtIndex:3];[changed concurrentDispatchThreadgroups:MTLSizeMake([specs[3][@"groups"]unsignedIntegerValue],1,1)threadsPerThreadgroup:MTLSizeMake([specs[3][@"local"]unsignedIntegerValue],1,1)];
  error=nil;NSUInteger staleEvents=stale.events.count;if([stale encodeProducerInCommandBuffer:[q commandBuffer]error:&error]||!error||stale.events.count!=staleEvents)return 49;
  [refusals addObject:@{@"case":@"destination_changed",@"refused":@YES,@"reason":error.localizedDescription,@"events_unchanged":@YES}];stale=nil;
  if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(3,1)error:&error])return 50;
  KPGPUCommandSelection*plan=[scope newGPUCommandGeometryFromBuffer:icb sourceRange:NSMakeRange(0,candidates)destination:icb destinationRange:NSMakeRange(candidates,rows)input:input inputOffset:128 nonce:nonce error:&error];if(!plan){fprintf(stderr,"%s\n",error.description.UTF8String);return 7;}choices=plan.choices;counts=plan.invocationCounts;geometry=plan.generatedGeometry;NSUInteger eventStart=scope.events.count;
  for(NSString*test in @[@"unretained_buffer",@"other_queue"]){id<MTLCommandBuffer>bad=[test isEqual:@"unretained_buffer"]?[q commandBufferWithUnretainedReferences]:[[d newCommandQueue]commandBuffer];error=nil;NSUInteger before=plan.events.count;if([plan encodeProducerInCommandBuffer:bad error:&error]||!error||plan.events.count!=before)return 42;[refusals addObject:@{@"case":test,@"refused":@YES,@"reason":error.localizedDescription,@"events_unchanged":@YES}];}

#endif
  auto readOutputs=[&]()->BOOL{id<MTLCommandBuffer>r=[q commandBuffer];id<MTLBlitCommandEncoder>bl=[r blitCommandEncoder];for(unsigned k=0;k<slots;k++){[bl copyFromBuffer:outputs[k]sourceOffset:0 toBuffer:hosts[k]destinationOffset:0 size:bytes];[bl copyFromBuffer:counters[k]sourceOffset:0 toBuffer:counterHosts[k]destinationOffset:0 size:208];}[bl endEncoding];return done(r);};
  if(!readOutputs())return 8;for(id<MTLBuffer>h in hosts)for(unsigned i=0;i<h.length;i++)if(((uint8_t*)h.contents)[i]!=0xa5)return 8;for(id<MTLBuffer>h in counterHosts){uint32_t n;memcpy(&n,(char*)h.contents+128,4);if(n)return 8;}
  id<MTLCommandBuffer>main=[q commandBuffer],pbuf=split?[q commandBuffer]:completed?[q commandBuffer]:main,sbuf=split?[q commandBuffer]:pbuf;
  if(producer){
#if KP_SELECT_NATIVE
   id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];[e setComputePipelineState:producerPSO];[e setBuffer:input offset:128 atIndex:0];[e setBuffer:choices offset:64 atIndex:1];[e setBuffer:counts offset:64 atIndex:2];[e setBuffer:producerConfig offset:0 atIndex:3];[e dispatchThreadgroups:MTLSizeMake(rows,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];
#else
   if(![plan encodeProducerInCommandBuffer:pbuf error:&error])return 9;
   for(NSString*test in @[@"producer_reencoded",@"pending_producer_other_buffer"]){id<MTLCommandBuffer>bad=[q commandBuffer];error=nil;NSUInteger before=plan.events.count;BOOL accepted=[test isEqual:@"producer_reencoded"]?[plan encodeProducerInCommandBuffer:bad error:&error]:[plan encodeSelectionInCommandBuffer:bad error:&error];if(accepted||!error||plan.events.count!=before)return 43;[refusals addObject:@{@"case":test,@"refused":@YES,@"reason":error.localizedDescription,@"events_unchanged":@YES}];}

#endif
  }
  if(split)[pbuf commit];
  if(selector){
#if KP_SELECT_NATIVE
   for(unsigned row=0;row<rows;row++){id<MTLComputeCommandEncoder>e=[sbuf computeCommandEncoder];[e setComputePipelineState:selectorPSO];[e setBuffer:argument offset:0 atIndex:0];[e setBuffer:choices offset:64 atIndex:1];[e setBuffer:counts offset:64+rows*4 atIndex:2];[e setBuffer:selectorConfigs[row]offset:0 atIndex:3];[e setBuffer:limits offset:0 atIndex:5];[e setBuffer:geometry offset:64 atIndex:6];[e useResource:icb usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(64,1,1)];[e endEncoding];}
#else
   if(![plan encodeSelectionInCommandBuffer:sbuf error:&error]){fprintf(stderr,"%s\n",error.description.UTF8String);return 10;}
#endif
  }
  #if !KP_SELECT_NATIVE
  error=nil;NSUInteger before=plan.events.count;if([plan encodeSelectionInCommandBuffer:[q commandBuffer]error:&error]||!error||plan.events.count!=before)return 44;[refusals addObject:@{@"case":@"selector_reencoded",@"refused":@YES,@"reason":error.localizedDescription,@"events_unchanged":@YES}];
  id<MTLIndirectComputeCommand>selectedCommand=[icb indirectComputeCommandAtIndex:3];
  for(NSString*test in @[@"set_pipeline_after_GPU",@"set_buffer_after_GPU",@"set_geometry_after_GPU",@"set_shared_after_GPU"]){BOOL caught=NO;NSString*reason=@"";@try{if([test isEqual:@"set_pipeline_after_GPU"])[selectedCommand setComputePipelineState:pipelines[names[0]]];else if([test isEqual:@"set_buffer_after_GPU"])[selectedCommand setKernelBuffer:outputs[0]offset:128 atIndex:0];else if([test isEqual:@"set_geometry_after_GPU"])[selectedCommand concurrentDispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];else[selectedCommand setThreadgroupMemoryLength:1024 atIndex:0];}@catch(NSException*x){caught=YES;reason=x.reason?:@"";}if(!caught||![reason isEqual:@"GPU-selected command requires reset before CPU re-encoding"])return 45;[refusals addObject:@{@"case":test,@"refused":@YES,@"reason":reason,@"events_unchanged":@YES}];}
  error=nil;if(KPCopyCPUICBCommands(icb,NSMakeRange(3,1),icb,0,&error)||!error)return 46;[refusals addObject:@{@"case":@"CPU_snapshot_GPU_selected",@"refused":@YES,@"reason":error.localizedDescription,@"events_unchanged":@YES}];
#endif
  if(split)[sbuf commit];if(completed){if(!done(pbuf))return 10;[icb resetWithRange:NSMakeRange(0,candidates)];}
  NSUInteger executeIndex=candidates;
  if(copy){b=[main blitCommandEncoder];
#if !KP_SELECT_NATIVE
   if(![scope adaptBlitEncoder:b error:&error])return 10;
#endif
   [b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(candidates,rows)destination:icb destinationIndex:candidates+rows];[b endEncoding];executeIndex+=rows;
  }
  id<MTLComputeCommandEncoder>e=[main computeCommandEncoder];
#if !KP_SELECT_NATIVE
  if(![scope adaptComputeEncoder:e error:&error])return 11;
#endif
  for(id<MTLBuffer>o in outputs)[e useResource:o usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(id<MTLBuffer>c in counters)[e useResource:c usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(id<MTLBuffer>p in params)[e useResource:p usage:MTLResourceUsageRead];[e executeCommandsInBuffer:icb withRange:NSMakeRange(executeIndex,rows)];[e endEncoding];
#if KP_SELECT_NATIVE
  NSArray*events=@[];NSArray*keep=@[icb,[pipelines.allValues copy],[params copy],argument,producerConfig,[selectorConfigs copy],limits,geometry];[main addCompletedHandler:^(id<MTLCommandBuffer>done){(void)keep.count;}];
#else
  NSArray*events=[scope.events subarrayWithRange:NSMakeRange(eventStart,scope.events.count-eventStart)];plan=nil;
#endif
  icb=nil;[params removeAllObjects];if(!prepare&&!done(main))return 12;
  if(!readOutputs())return 13;id<MTLBuffer>geometryHost=[d newBufferWithLength:geometry.length options:MTLResourceStorageModeShared],choiceHost=[d newBufferWithLength:choices.length options:MTLResourceStorageModeShared],countHost=[d newBufferWithLength:counts.length options:MTLResourceStorageModeShared];id<MTLCommandBuffer>read=[q commandBuffer];b=[read blitCommandEncoder];[b copyFromBuffer:geometry sourceOffset:0 toBuffer:geometryHost destinationOffset:0 size:geometry.length];[b copyFromBuffer:choices sourceOffset:0 toBuffer:choiceHost destinationOffset:0 size:choices.length];[b copyFromBuffer:counts sourceOffset:0 toBuffer:countHost destinationOffset:0 size:counts.length];[b copyFromBuffer:input sourceOffset:0 toBuffer:inputRead destinationOffset:0 size:input.length];[b endEncoding];if(!done(read))return 13;
  NSMutableArray*files=[NSMutableArray new],*countFiles=[NSMutableArray new];for(unsigned k=0;k<slots;k++){NSString*n=[NSString stringWithFormat:@"trial-%u-slot-%u.bin",t,k],*cn=[NSString stringWithFormat:@"trial-%u-counter-%u.bin",t,k];id<MTLBuffer>h=hosts[k],ch=counterHosts[k];[[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:n]atomically:YES];[[NSData dataWithBytes:ch.contents length:ch.length]writeToFile:[out stringByAppendingPathComponent:cn]atomically:YES];[files addObject:n];[countFiles addObject:cn];}
  NSString*cf=[NSString stringWithFormat:@"trial-%u-choices.bin",t],*pf=[NSString stringWithFormat:@"trial-%u-invocations.bin",t],*vf=[NSString stringWithFormat:@"trial-%u-input.bin",t],*gf=[NSString stringWithFormat:@"trial-%u-geometry.bin",t];for(NSArray*x in @[@[gf,geometryHost],@[cf,choiceHost],@[pf,countHost],@[vf,inputRead]]){id<MTLBuffer>h=x[1];[[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:x[0]]atomically:YES];}
  [runs addObject:@{@"trial":@(t),@"nonce":@(nonce),@"node_specs":specs,@"outputs":files,@"counter_files":countFiles,@"choice_file":cf,@"invocation_file":pf,@"input_file":vf,@"geometry_file":gf,@"events":events,@"refusals":refusals,@"committed":@(!prepare),@"command_status":@(main.status),@"initial_outputs_untouched_after_preparation":@YES,@"source_reset_after_completed_selector":@(completed),@"ICB_and_parameter_external_refs_released_before_commit":@YES,@"intermediate_CPU_completion_waits":@(completed?1:0),@"execute_index":@(executeIndex)}];
 }}
#if !KP_SELECT_NATIVE
 [scope restore];
#endif
 emit(@{@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),@"native_reference":@(KP_SELECT_NATIVE!=0),@"candidate_count":@(candidates),@"rows":@(rows),@"slots":@(slots),@"runs":runs,@"scope_restored":@(object_getClass(d)==original),@"system_modified":@NO,@"choice_CPU_read_before_execution":@NO,@"CPU_expected_answers_uploaded":@NO,@"performance_benchmark":@NO,@"GPU_generated_X_grid":@YES,@"general_GPU_ICB_encoding":@NO});return 0;
}}
