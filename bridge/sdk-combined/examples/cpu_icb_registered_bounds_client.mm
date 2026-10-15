#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#define KP_REGISTERED_NATIVE 0
struct P{uint32_t count,seed,salt,stage;};
static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char x:h)[s appendFormat:@"%02x",x];return s;}
static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static void emit(id x){NSData*j=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);BOOL cold=[mode isEqual:@"prepare_short"],prepare=NO,completed=NO;NSUInteger width=2,slots=6;if(!cold&&![mode isEqual:@"copy_short"])return 1;
 id<MTLDevice>d=nil;
#if KP_REGISTERED_NATIVE
 d=MTLCreateSystemDefaultDevice();
#else
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;
#endif
 if(!d)return 2;Class original=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 NSData*library=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"literal_lut.metallib"]],*manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"cpu_icb_literal_lut_manifest.json"]];NSArray*names=@[@"literal_lut_16",@"literal_lut_64",@"literal_lut_128",@"literal_lut_256"];NSMutableDictionary*pipelines=[NSMutableDictionary dictionary];
#if KP_REGISTERED_NATIVE
 id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"literal_lut.metallib"]]error:&error];if(!lib)return 3;
 for(NSString*n in names){MTLComputePipelineDescriptor*desc=[MTLComputePipelineDescriptor new];desc.computeFunction=[lib newFunctionWithName:n];desc.supportIndirectCommandBuffers=YES;id<MTLComputePipelineState>p=[d newComputePipelineStateWithDescriptor:desc options:MTLPipelineOptionNone reflection:nil error:&error];if(!p)return 3;pipelines[n]=p;}
#else
 KPCPUICBScope*scope=[KPCPUICBScope installOnDevice:d queue:q libraryData:library expectedSHA256:sha(library)manifestData:manifest expectedManifestSHA256:sha(manifest)error:&error];if(!scope){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}for(NSString*n in names)pipelines[n]=[scope pipelineForFunction:n];
#endif
 const NSUInteger bytes=8192*16+512;const unsigned tableIndices[3][6]={{0,2,3,1,0,3},{2,3,0,3,1,2},{3,0,2,0,3,1}},baseCounts[3]={65,2057,4113},baseLocals[6]={32,64,128,256,512,1024};NSMutableArray*runs=[NSMutableArray array];
 for(unsigned t=0;t<3;t++){@autoreleasepool{
  NSMutableArray*outputs=[NSMutableArray array],*host=[NSMutableArray array],*params=[NSMutableArray array],*specs=[NSMutableArray array];
  id<MTLBuffer>input=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate],upload=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared],inputRead=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared],counter=[d newBufferWithLength:208 options:MTLResourceStorageModePrivate],counterHost=[d newBufferWithLength:208 options:MTLResourceStorageModeShared];if(!input||!upload||!inputRead||!counter||!counterHost)return 4;
  memset(upload.contents,0xa5,bytes);for(unsigned i=0;i<8192;i++){uint32_t v[4]={i*11u+0x73193211u,(i^0x11998877u)+97u*t,(i*65537u)^0x7719u,(i+0x4d2713u+t*97u)*13u};memcpy((char*)upload.contents+256+i*16,v,16);}
  for(unsigned k=0;k<slots;k++){id<MTLBuffer>o=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate],h=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared],p=[d newBufferWithLength:2048 options:MTLResourceStorageModeShared];if(!o||!h||!p)return 4;unsigned n=baseCounts[t]+k*17,l=baseLocals[k],seed=0x4d2713+t*97+k*29,salt=0x7719+t*53+k*71;P v={n,seed,salt,k};memset(p.contents,0xa5,p.length);memcpy((char*)p.contents+1024,&v,16);memset(h.contents,0xa5,bytes);[outputs addObject:o];[host addObject:h];[params addObject:p];[specs addObject:@{@"function":names[tableIndices[t][k]],@"count":@(n),@"local":@(l),@"groups":@((n+l-1)/l),@"seed":@(seed),@"salt":@(salt),@"stage":@(k)}];}
  memset(counterHost.contents,0xa5,208);memset((char*)counterHost.contents+128,0,24);
  id<MTLCommandBuffer>init=[q commandBuffer];id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];[b copyFromBuffer:upload sourceOffset:0 toBuffer:input destinationOffset:0 size:bytes];[b copyFromBuffer:counterHost sourceOffset:0 toBuffer:counter destinationOffset:0 size:208];for(unsigned k=0;k<slots;k++)[b copyFromBuffer:host[k]sourceOffset:0 toBuffer:outputs[k]destinationOffset:0 size:bytes];[b endEncoding];if(!done(init))return 5;
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;desc.maxKernelBufferBindCount=4;id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:slots options:MTLResourceStorageModeShared];if(!icb)return 6;
  for(unsigned k=0;k<slots;k++){NSDictionary*s=specs[k];id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:k];[c setComputePipelineState:pipelines[s[@"function"]]];[c setKernelBuffer:outputs[k]offset:128 atIndex:0];[c setKernelBuffer:input offset:256 atIndex:1];[c setKernelBuffer:params[k]offset:1024 atIndex:2];[c setKernelBuffer:counter offset:128 atIndex:3];[c concurrentDispatchThreadgroups:MTLSizeMake([s[@"groups"]unsignedIntegerValue],1,1)threadsPerThreadgroup:MTLSizeMake([s[@"local"]unsignedIntegerValue],1,1)];}
  id<MTLBuffer>shortInput=[d newBufferWithLength:16 options:MTLResourceStorageModePrivate];if(!shortInput)return 7;NSUInteger badIndex=cold?5:3;BOOL rejected=NO;NSString*reason=nil;BOOL noPreparationSideEffects=NO;NSUInteger eventStart=scope.events.count;
  if(cold){[[icb indirectComputeCommandAtIndex:badIndex]setKernelBuffer:shortInput offset:0 atIndex:1];rejected=![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots)error:&error];reason=error.localizedDescription;noPreparationSideEffects=scope.events.count==eventStart;}
  else{if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots)error:&error])return 7;[[icb indirectComputeCommandAtIndex:badIndex]setKernelBuffer:shortInput offset:0 atIndex:1];id<MTLCommandBuffer>bad=[q commandBuffer];id<MTLBlitCommandEncoder>b=[bad blitCommandEncoder];if(![scope adaptBlitEncoder:b error:&error])return 7;eventStart=scope.events.count;@try{[b copyIndirectCommandBuffer:icb sourceRange:NSMakeRange(0,2)destination:icb destinationIndex:2];}@catch(NSException*x){rejected=YES;reason=x.reason;}noPreparationSideEffects=scope.events.count==eventStart;[b endEncoding];if(bad.status!=0)return 7;}
  if(!rejected||!noPreparationSideEffects||![reason containsString:@"Resident schema2 buffer range is insufficient"])return 8;
  NSUInteger activeIndex=cold?0:2;id<MTLCommandBuffer>main=[q commandBuffer];id<MTLComputeCommandEncoder>e=[main computeCommandEncoder];if(![scope adaptComputeEncoder:e error:&error])return 9;[e executeCommandsInBuffer:icb withRange:NSMakeRange(activeIndex,1)];[e endEncoding];NSArray*events=[scope.events subarrayWithRange:NSMakeRange(eventStart,scope.events.count-eventStart)];
  icb=nil;[params removeAllObjects];
  auto readback=[&]()->BOOL{id<MTLCommandBuffer>r=[q commandBuffer];id<MTLBlitCommandEncoder>bl=[r blitCommandEncoder];for(unsigned k=0;k<slots;k++)[bl copyFromBuffer:outputs[k]sourceOffset:0 toBuffer:host[k]destinationOffset:0 size:bytes];[bl copyFromBuffer:input sourceOffset:0 toBuffer:inputRead destinationOffset:0 size:bytes];[bl copyFromBuffer:counter sourceOffset:0 toBuffer:counterHost destinationOffset:0 size:208];[bl endEncoding];return done(r);};
  if(!readback())return 10;for(id<MTLBuffer>h in host)for(unsigned i=0;i<bytes;i++)if(((uint8_t*)h.contents)[i]!=0xa5)return 10;for(unsigned i=0;i<6;i++){uint32_t c=99;memcpy(&c,(char*)counterHost.contents+128+i*4,4);if(c)return 10;}
  if(!prepare&&!done(main))return 11;if(!readback())return 12;NSMutableArray*files=[NSMutableArray array];
  for(unsigned k=0;k<slots;k++){id<MTLBuffer>h=host[k];NSString*n=[NSString stringWithFormat:@"trial-%u-slot-%u.bin",t,k];if(![[NSData dataWithBytes:h.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:n]atomically:YES])return 13;[files addObject:n];}
  NSString*cn=[NSString stringWithFormat:@"trial-%u-counter.bin",t],*in=[NSString stringWithFormat:@"trial-%u-input.bin",t];[[NSData dataWithBytes:counterHost.contents length:208]writeToFile:[out stringByAppendingPathComponent:cn]atomically:YES];[[NSData dataWithBytes:inputRead.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:in]atomically:YES];
  [runs addObject:@{@"trial":@(t),@"node_specs":specs,@"outputs":files,@"counter_file":cn,@"input_file":in,@"copy_events":events,@"committed":@(!prepare),@"command_status":@(main.status),@"before_commit_untouched":@YES,@"source_reset_after_completed_producer":@(completed),@"refused":@(rejected),@"refusal_reason":reason,@"no_events_before_refusal":@(noPreparationSideEffects),@"active_index":@(activeIndex),@"undersized_input_bytes":@16,@"ICB_and_parameter_external_refs_released_before_commit":@YES}];
 }}
#if !KP_REGISTERED_NATIVE
 [scope restore];
#endif
 emit(@{@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),@"native_reference":@(KP_REGISTERED_NATIVE!=0),@"width":@(width),@"slots":@(slots),@"runs":runs,@"scope_restored":@(object_getClass(d)==original),@"system_modified":@NO,@"CPU_expected_answers_uploaded":@NO,@"intermediate_descriptor_CPU_readback":@NO,@"performance_benchmark":@NO,@"full_ICB_contract":@NO});return 0;
}}
