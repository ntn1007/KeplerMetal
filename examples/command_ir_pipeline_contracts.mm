#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#ifndef KP_PUBLIC_ARGUMENT_ENCODER
#define KP_PUBLIC_ARGUMENT_ENCODER 0
#endif
#ifndef KP_FUNCTION_ARGUMENT_ENCODER
#define KP_FUNCTION_ARGUMENT_ENCODER 0
#endif
#ifndef KP_ARGUMENT_REFUSALS
#define KP_ARGUMENT_REFUSALS 0
#endif
#if !KP_DATAFLOW_NATIVE
#import "KeplerProgramImport.h"
#endif
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#include "PipelineFactoryReception.inc"
#include "QueueFactoryReception.inc"
#include "LibraryFunctionReception.inc"
struct Push{uint64_t root;uint32_t grid[3],local[3];};
static id<MTLArgumentEncoder>publicArgumentEncoder(id<MTLDevice>d){NSMutableArray*a=[NSMutableArray new];for(unsigned i=0;i<6;i++){MTLArgumentDescriptor*x=[MTLArgumentDescriptor argumentDescriptor];x.index=i;x.arrayLength=1;x.access=MTLArgumentAccessReadOnly;x.dataType=i==0?MTLDataTypeIndirectCommandBuffer:i==1?MTLDataTypeComputePipeline:MTLDataTypePointer;[a addObject:x];}return[d newArgumentEncoderWithArguments:a];}
#if !KP_DATAFLOW_NATIVE && KP_ARGUMENT_REFUSALS
#include "PublicArgumentRefusals.inc"
#endif
static NSString*hash(NSData*d){unsigned char b[32];CC_SHA256(d.bytes,(CC_LONG)d.length,b);NSMutableString*s=[NSMutableString new];for(unsigned char x:b)[s appendFormat:@"%02x",x];return s;}
static void emit(id x){NSData*d=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}
static BOOL done(id<MTLCommandBuffer>b){[b commit];[b waitUntilCompleted];return b.status==MTLCommandBufferStatusCompleted;}
static id<MTLLibrary>load(id<MTLDevice>d,NSString*p,NSError**e){return[d newLibraryWithURL:[NSURL fileURLWithPath:p]error:e];}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
 NSUInteger factoryKind=0;NSDictionary*factoryEvidence=nil;NSArray*parts=[mode componentsSeparatedByString:@":"];if(parts.count==6){receptionLibraryKind=[parts[3]integerValue];receptionFunctionKind=[parts[4]integerValue];if(receptionLibraryKind>2||receptionFunctionKind>8||![[NSString stringWithFormat:@"%lu",(unsigned long)receptionLibraryKind]isEqual:parts[3]]||![[NSString stringWithFormat:@"%lu",(unsigned long)receptionFunctionKind]isEqual:parts[4]])return 1;parts=@[parts[0],parts[1],parts[2],parts[5]];}if(parts.count==4){receptionQueueKind=[parts[1]integerValue];receptionEncoderKind=[parts[2]integerValue];if(receptionQueueKind>1||receptionEncoderKind>4||![[NSString stringWithFormat:@"%lu",(unsigned long)receptionQueueKind]isEqual:parts[1]]||![[NSString stringWithFormat:@"%lu",(unsigned long)receptionEncoderKind]isEqual:parts[2]])return 1;parts=@[parts[0],parts[3]];}if(parts.count==2){factoryKind=[parts[0]integerValue];if(factoryKind>5||![[NSString stringWithFormat:@"%lu",(unsigned long)factoryKind]isEqual:parts[0]])return 1;mode=parts[1];}else if(parts.count!=1)return 1;
 BOOL reuseEncoder=[mode isEqual:@"encoder_reuse"];id<MTLArgumentEncoder>reusableEncoder=nil;__weak id priorArgumentPlan=nil;
 BOOL producer=![mode isEqual:@"no_producer"],consumerPresent=![mode isEqual:@"no_consumer"],copy=[mode isEqual:@"copy"],split=[mode isEqual:@"split"],bad=[mode hasPrefix:@"bad_"];NSUInteger rows=copy?4:3,slots=3+rows;
 NSString*semantic=(!producer||!consumerPresent||split||bad||reuseEncoder||[mode isEqual:@"refusals"])?@"basic":mode;
 if(![@[@"basic",@"barrier",@"copy",@"no_seed",@"no_gather",@"no_finish"]containsObject:semantic])return 1;
 id<MTLDevice>d=nil;
#if KP_DATAFLOW_NATIVE
 d=MTLCreateSystemDefaultDevice();if(![d.name isEqual:@"Apple M1 Max"]||bad||[mode isEqual:@"refusals"])return 2;
#else
 for(id<MTLDevice>x in MTLCopyAllDevices())if(KPKepler880MIdentity(x)){if(d)return 2;d=x;}
#endif
 if(!d)return 2;id<MTLCommandQueue>q=[d newCommandQueue];Class original=object_getClass(d);NSError*error=nil;KPCPUICBScope*scope=nil;NSMutableArray*pipelines=[NSMutableArray new];NSArray*names=@[@"dependency_seed",@"dependency_gather",@"dependency_finish"];
 NSDictionary*info=@{},*importProof=@{};id<MTLComputePipelineState>writer=nil,fieldPSO=nil;id<MTLFunction>producerFunction=nil;
#if KP_DATAFLOW_NATIVE
 id<MTLLibrary>lib=load(d,[assets stringByAppendingPathComponent:@"consumer.metallib"],&error);for(NSString*n in names){MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=[lib newFunctionWithName:n];p.supportIndirectCommandBuffers=YES;id<MTLComputePipelineState>x=[d newComputePipelineStateWithDescriptor:p options:MTLPipelineOptionNone reflection:nil error:&error];if(!x){emit(@{@"failure":@"library-function-preflight",@"check":@0,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}[pipelines addObject:x];}
 id<MTLLibrary>p=receptionLoadLibrary(d,[assets stringByAppendingPathComponent:@"producer.metallib"],&error);producerFunction=receptionLibraryFunction(p,[@"encode_dataflow_" stringByAppendingString:semantic],&error);writer=receptionPipeline(d,producerFunction,factoryKind,&factoryEvidence,&error);
#else
 NSData*lib=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.metallib"]],*manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.json"]];if(![hash(lib)isEqual:@"7b415aef3f5feb660698dfa0816b11a62d35da9ccc71cd83be170fabd904349f"]){emit(@{@"failure":@"library-function-preflight",@"check":@1,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}
 scope=[KPCPUICBScope installOnDevice:d queue:q libraryData:lib expectedSHA256:hash(lib)manifestData:manifest expectedManifestSHA256:hash(manifest)error:&error];if(!scope){emit(@{@"failure":@"register",@"error":error.description?:@"nil"});{emit(@{@"failure":@"library-function-preflight",@"check":@2,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}}for(NSString*n in names)[pipelines addObject:[scope pipelineForFunction:n]];
 for(NSArray*a in @[@[@"gpu_command_selector.metallib",@0],@[@"gpu_command_geometry.metallib",@1],@[@"gpu_command_bindings.metallib",@2],@[@"materializer.metallib",@3]]){NSData*b=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:a[0]]];BOOL ok=NO;switch([a[1]intValue]){case 0:ok=[scope enableGPUCommandSelectionWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 1:ok=[scope enableGPUCommandGeometryWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 2:ok=[scope enableGPUCommandBindingsWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 3:ok=[scope enableGPUCommandIRv2WithLibraryData:b expectedSHA256:hash(b)error:&error];}if(!ok){emit(@{@"failure":@"enable",@"error":error.description?:@"nil"});{emit(@{@"failure":@"library-function-preflight",@"check":@3,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}}}
 info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[semantic stringByAppendingString:@".json"]]]options:0 error:nil];if([info[@"command_ir_version"]intValue]!=2||[info[@"sm"]intValue]!=30||[info[@"buffer_slots"]intValue]!=1||[info[@"push_bytes"]intValue]!=32||[info[@"grid_offset"]intValue]!=8||[info[@"scratch_bytes"]intValue]||[info[@"crs_bytes"]intValue]){emit(@{@"failure":@"library-function-preflight",@"check":@4,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}
 id<MTLLibrary>f=load(d,[assets stringByAppendingPathComponent:@"field.metallib"],&error);fieldPSO=[d newComputePipelineStateWithFunction:[f newFunctionWithName:@"mutate_command_ir_data"]error:&error];
#endif
#if KP_FUNCTION_ARGUMENT_ENCODER && !KP_DATAFLOW_NATIVE
 id<MTLLibrary>unregistered=load(d,[assets stringByAppendingPathComponent:@"producer.metallib"],&error);NSError*nativeError=nil;
 if([d newComputePipelineStateWithFunction:[unregistered newFunctionWithName:[@"encode_dataflow_" stringByAppendingString:semantic]]error:&nativeError]||![nativeError.description containsString:@"air.compute_pipeline_state"]){emit(@{@"failure":@"library-function-preflight",@"check":@5,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}
 if(!receptionRegisterLibrary(scope,assets,&error)){emit(@{@"failure":@"library-function-preflight",@"check":@6,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}id<MTLLibrary>registeredSource=receptionLoadLibrary(d,[assets stringByAppendingPathComponent:@"producer.metallib"],&error);producerFunction=receptionLibraryFunction(registeredSource,[@"encode_dataflow_" stringByAppendingString:semantic],&error);if(!producerFunction){emit(@{@"failure":@"library-function-preflight",@"check":@7,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}
 writer=receptionPipeline(d,producerFunction,factoryKind,&factoryEvidence,&error);id<MTLComputePipelineState>cached=[d newComputePipelineStateWithFunction:producerFunction error:&error];
 if(!writer||(factoryKind==0&&writer!=cached)||![NSStringFromClass(object_getClass(writer))isEqual:@"NVMTLComputePipelineState"]){emit(@{@"failure":@"library-function-preflight",@"check":@8,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}
 for(NSDictionary*event in scope.events)if([event[@"operation"]isEqual:@"register_IRv2_native_producer"])importProof=event[@"profile"][@"import"];
 importProof=objc_getAssociatedObject(writer,sel_registerName("KeplerMetalProducerEvidence-v1"));if(![importProof[@"contract_verified"]boolValue]){emit(@{@"failure":@"library-function-preflight",@"check":@9,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}
 id<MTLLibrary>ordinary=load(d,[assets stringByAppendingPathComponent:@"consumer.metallib"],&error);id<MTLComputePipelineState>untouched=[d newComputePipelineStateWithFunction:[ordinary newFunctionWithName:@"dependency_seed"]error:&error];if(!untouched){emit(@{@"failure":@"library-function-preflight",@"check":@10,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}


#endif
 if(!writer){emit(@{@"failure":@"library-function-preflight",@"check":@11,@"error":error.description?:@"",@"factory_evidence":factoryEvidence?:@{},@"library_events":scope.events?:@[],@"runs":@[]});return 3;}unsigned sizes[4]={256,1024,4096,32768},locals[4][3]={{32,128,1024},{33,256,512},{128,33,1024},{1024,256,33}};NSUInteger APIrefusals=0;NSMutableArray*runs=[NSMutableArray new];
 for(unsigned trial=0;trial<4;trial++){@autoreleasepool{
  unsigned n=sizes[trial],maximum=0;for(unsigned k=0;k<3;k++)maximum=MAX(maximum,((n+locals[trial][k]-1)/locals[trial][k])*locals[trial][k]);NSUInteger bytes=maximum*16+512;
  NSMutableDictionary*buffers=[NSMutableDictionary new],*hosts=[NSMutableDictionary new];
  auto allocate=[&](NSString*name,NSUInteger length){id<MTLBuffer>b=[d newBufferWithLength:length options:MTLResourceStorageModePrivate],h=[d newBufferWithLength:length options:MTLResourceStorageModeShared];if(!b||!h)return false;buffers[name]=b;hosts[name]=h;memset(h.contents,0xa5,length);return true;};
  for(NSString*name in @[@"input",@"stage0",@"stage1",@"stage2",@"dummySrc"])if(!allocate(name,bytes))return 4;
  if(!allocate(@"counter",256)||!allocate(@"dummyCounter",256)||!allocate(@"records",1216))return 4;
  for(NSString*name in @[@"counter",@"dummyCounter"]){id<MTLBuffer>h=hosts[name];memset((char*)h.contents+128,0,12);}
  NSMutableArray*params=[NSMutableArray new],*specs=[NSMutableArray new];
  for(unsigned k=0;k<slots;k++){unsigned stage=k%3,seed=0x13579+trial*97+stage*101,salt=0x7654321+trial*31+stage*137;NSString*name=[NSString stringWithFormat:@"dummy%u",k];if(!allocate(name,bytes))return 4;id<MTLBuffer>p=[d newBufferWithLength:1536 options:MTLResourceStorageModeShared];if(!p)return 4;memset(p.contents,0xa5,p.length);uint32_t words[8]={n,seed,salt,stage,locals[trial][stage],0,0,0};memcpy((char*)p.contents+256,words,sizeof words);[params addObject:p];if(k<3)[specs addObject:@{@"stage":@(stage),@"count":@(n),@"seed":@(seed),@"salt":@(salt),@"local":@(words[4]),@"groups":@((n+words[4]-1)/words[4])}];}
  id<MTLCommandBuffer>init=receptionCommandBuffer(q);id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];for(NSString*name in buffers){id<MTLBuffer>h=hosts[name];[b copyFromBuffer:h sourceOffset:0 toBuffer:buffers[name]destinationOffset:0 size:h.length];}[b endEncoding];if(!done(init))return 5;
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=4;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:slots options:MTLResourceStorageModeShared];if(!icb)return 6;
  for(unsigned k=0;k<slots;k++){unsigned stage=k%3;id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:k];[c setComputePipelineState:pipelines[stage]];[c setKernelBuffer:buffers[[NSString stringWithFormat:@"dummy%u",k]]offset:128 atIndex:0];if(stage)[c setKernelBuffer:buffers[@"dummySrc"]offset:128 atIndex:1];[c setKernelBuffer:params[k]offset:256 atIndex:2];[c setKernelBuffer:buffers[@"dummyCounter"]offset:128 atIndex:3];[c concurrentDispatchThreadgroups:MTLSizeMake((n+locals[trial][stage]-1)/locals[trial][stage],1,1)threadsPerThreadgroup:MTLSizeMake(locals[trial][stage],1,1)];}
  id<MTLIndirectCommandBuffer>target=icb;NSUInteger first=3;id<MTLBuffer>root=nil,witness=nil,witnessHost=nil;KPGPUCommandSelection*plan=nil;
#if KP_DATAFLOW_NATIVE
  target=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:rows options:MTLResourceStorageModeShared];[target resetWithRange:NSMakeRange(0,rows)];first=0;id<MTLArgumentEncoder>ae=(KP_FUNCTION_ARGUMENT_ENCODER||!KP_PUBLIC_ARGUMENT_ENCODER)?[producerFunction newArgumentEncoderWithBufferIndex:0]:publicArgumentEncoder(d);if(ae.encodedLength!=48){emit(@{@"failure":@"root_stride",@"actual":@(ae.encodedLength)});return 7;}root=[d newBufferWithLength:144 options:MTLResourceStorageModeShared];
  for(unsigned stage=0;stage<3;stage++){[ae setArgumentBuffer:root offset:stage*48];[ae setIndirectCommandBuffer:target atIndex:0];[ae setComputePipelineState:pipelines[stage]atIndex:1];[ae setBuffer:buffers[[@"stage" stringByAppendingFormat:@"%u",stage]]offset:128 atIndex:2];[ae setBuffer:buffers[stage?[@"stage" stringByAppendingFormat:@"%u",stage-1]:@"input"]offset:128 atIndex:3];[ae setBuffer:params[stage]offset:256 atIndex:4];[ae setBuffer:buffers[@"counter"]offset:128 atIndex:5];}
#else
  if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots)error:&error]){emit(@{@"failure":@"prepare",@"error":error.description?:@"nil"});return 7;}
  NSMutableArray*entries=[NSMutableArray new];for(unsigned stage=0;stage<3;stage++)[entries addObject:@{@"bindings":@[@{@"buffer":buffers[[@"stage" stringByAppendingFormat:@"%u",stage]],@"offset":@128},@{@"buffer":buffers[stage?[@"stage" stringByAppendingFormat:@"%u",stage-1]:@"input"],@"offset":@128},@{@"buffer":buffers[@"counter"],@"offset":@128}]}];
  if(trial==0&&[mode isEqual:@"refusals"]){
   id command=[icb indirectComputeCommandAtIndex:0];id native=[command valueForKey:@"record"];
   for(NSString*test in @[@"duplicate_entry",@"intra_entry_alias",@"partial_overlap",@"descriptor_records_alias",@"original_binding_alias",@"unaligned",@"undersized",@"wrong_entry_type"]){NSArray*catalogue=entries;id<MTLBuffer>records=buffers[@"records"];NSUInteger off=128;
    if([test isEqual:@"duplicate_entry"])catalogue=@[entries[0],entries[0]];
    else if([test isEqual:@"descriptor_records_alias"]){records=[native valueForKey:@"descriptor"];off=0;}
    else if([test isEqual:@"wrong_entry_type"])catalogue=@[NSNull.null];
    else{NSMutableArray*e=[entries mutableCopy],*bindings=[entries[[test isEqual:@"partial_overlap"]?1:0][@"bindings"]mutableCopy];NSUInteger slot=[test isEqual:@"partial_overlap"]?2:0;NSMutableDictionary*v=[bindings[slot]mutableCopy];if([test isEqual:@"intra_entry_alias"])v[@"buffer"]=bindings[1][@"buffer"];if([test isEqual:@"partial_overlap"])v[@"offset"]=@132;if([test isEqual:@"original_binding_alias"])v[@"buffer"]=buffers[@"dummy0"];if([test isEqual:@"unaligned"])v[@"offset"]=@129;if([test isEqual:@"undersized"]){v[@"buffer"]=[d newBufferWithLength:16 options:MTLResourceStorageModePrivate];v[@"offset"]=@0;}bindings[slot]=v;e[[test isEqual:@"partial_overlap"]?1:0]=@{@"bindings":bindings};catalogue=e;}
    NSError*rejection=nil;id invalid=[scope newGPUCommandIRv2FromBuffer:icb sourceRange:NSMakeRange(0,3)destination:icb destinationRange:NSMakeRange(3,rows)resources:catalogue records:records recordOffset:off error:&rejection];if(invalid||!rejection){emit(@{@"failure":@"API_refusal",@"case":test});return 21;}APIrefusals++;
   }
  }
  plan=[scope newGPUCommandIRv2FromBuffer:icb sourceRange:NSMakeRange(0,3)destination:icb destinationRange:NSMakeRange(3,rows)resources:entries records:buffers[@"records"]recordOffset:128 error:&error];if(!plan){emit(@{@"failure":@"plan",@"error":error.description?:@"nil"});return 8;}
#if KP_ARGUMENT_REFUSALS
  plan=nil;NSArray*refusals=runPublicArgumentRefusals(d,scope,icb,entries,buffers,params,pipelines,writer,trial);[runs addObject:@{@"trial":@(trial),@"argument_refusals":refusals}];continue;
#endif
  root=[d newBufferWithLength:144 options:MTLResourceStorageModeShared];
#if KP_PUBLIC_ARGUMENT_ENCODER
  __weak id weakAE=nil;
  @autoreleasepool{MTLArgument*reflection=nil;id<MTLArgumentEncoder>ae=reusableEncoder;
   if(!ae){if(KP_FUNCTION_ARGUMENT_ENCODER)ae=trial%2?[producerFunction newArgumentEncoderWithBufferIndex:0 reflection:&reflection]:[producerFunction newArgumentEncoderWithBufferIndex:0];else ae=publicArgumentEncoder(d);}
   if(KP_FUNCTION_ARGUMENT_ENCODER&&!reusableEncoder&&trial%2&&(!reflection||reflection.bufferDataSize!=48||reflection.bufferStructType.members.count!=6))return 8;
   weakAE=ae;if(reuseEncoder)reusableEncoder=ae;if(ae.encodedLength!=48||ae.alignment!=8)return 8;
   for(unsigned binding=0;binding<4;binding++){unsigned stage=binding%3;[ae setArgumentBuffer:root startOffset:0 arrayElement:stage];
    if(binding==3){id<MTLIndirectCommandBuffer> __unsafe_unretained ib[1]={target};id<MTLComputePipelineState> __unsafe_unretained ps[1]={pipelines[stage]};id<MTLBuffer> __unsafe_unretained bs[4]={buffers[@"stage0"],buffers[@"input"],params[stage],buffers[@"counter"]};NSUInteger offsets[4]={128,128,256,128};[ae setIndirectCommandBuffers:ib withRange:NSMakeRange(0,1)];[ae setComputePipelineStates:ps withRange:NSMakeRange(1,1)];[ae setBuffers:bs offsets:offsets withRange:NSMakeRange(2,4)];}
    else{[ae setIndirectCommandBuffer:target atIndex:0];[ae setComputePipelineState:pipelines[stage]atIndex:1];[ae setBuffer:buffers[[@"stage" stringByAppendingFormat:@"%u",stage]]offset:128 atIndex:2];[ae setBuffer:buffers[stage?[@"stage" stringByAppendingFormat:@"%u",stage-1]:@"input"]offset:128 atIndex:3];[ae setBuffer:params[stage]offset:256 atIndex:4];[ae setBuffer:buffers[@"counter"]offset:128 atIndex:5];}
   }
  }
  if(weakAE&&!reuseEncoder){emit(@{@"failure":@"argument_encoder_lifetime"});return 8;}
  if(reuseEncoder){if(priorArgumentPlan){emit(@{@"failure":@"previous_argument_plan_lifetime"});return 8;}priorArgumentPlan=plan;}
  __weak id weakNative=nil;@autoreleasepool{MTLArgumentDescriptor*a=[MTLArgumentDescriptor argumentDescriptor];a.index=0;a.dataType=MTLDataTypePointer;a.arrayLength=1;id<MTLArgumentEncoder>e=[d newArgumentEncoderWithArguments:@[a]];weakNative=e;if(e.encodedLength!=8||e.alignment!=8||![NSStringFromClass(object_getClass(e))isEqual:@"NVMTLIndirectArgumentEncoder"])return 8;id<MTLBuffer>b=[d newBufferWithLength:8 options:MTLResourceStorageModeShared];[e setArgumentBuffer:b offset:0];[e setBuffer:buffers[@"counter"]offset:128 atIndex:0];}if(weakNative){emit(@{@"failure":@"native_encoder_lifetime"});return 8;}
  if(![plan validateCommandIRArgumentBindings:&error]){emit(@{@"failure":@"public_argument_bindings",@"error":error.description?:@"nil"});return 8;}
#else
  for(unsigned stage=0;stage<3;stage++){id<MTLBuffer>r=[plan newCommandIRArgumentsForCandidateIndex:stage resourceIndex:stage error:&error];if(r.length!=48)return 8;memcpy((char*)root.contents+stage*48,r.contents,48);}
#endif
  witness=plan.generatedGeometry;witnessHost=[d newBufferWithLength:witness.length options:MTLResourceStorageModeShared];
#endif
  id<MTLCommandBuffer>main=receptionCommandBuffer(q),pbuf=split?receptionCommandBuffer(q):main;
  if(producer){id<MTLComputeCommandEncoder>e=receptionComputeEncoder(pbuf);
#if !KP_DATAFLOW_NATIVE
if(![NSStringFromClass(object_getClass(e))hasPrefix:@"KPICBEncoder_"])return 10;
#endif
[e setComputePipelineState:writer];
#if KP_DATAFLOW_NATIVE
   [e setBuffer:root offset:0 atIndex:0];[e useResource:target usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(id<MTLBuffer>r in buffers.allValues)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(id<MTLBuffer>r in params)[e useResource:r usage:MTLResourceUsageRead];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];
#else
    [e setBuffer:root offset:0 atIndex:0];[e useResource:root usage:MTLResourceUsageRead];for(id<MTLBuffer>r in plan.commandIRProducerResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];NSArray*keep=@[root,writer,plan.commandIRProducerResources];[pbuf addCompletedHandler:^(id<MTLCommandBuffer>c){(void)keep.count;}];
#endif
   [e endEncoding];}
#if !KP_DATAFLOW_NATIVE
  if(bad){NSDictionary*changes=@{@"bad_parameters":@[@16,@1],@"bad_counter":@[@26,@1],@"bad_pipeline":@[@2,@8],@"bad_buffer3_flag":@[@1,@115],@"bad_groups":@[@4,@0],@"bad_reserved":@[@28,@1]};NSArray*c=changes[mode];if(!c)return 9;uint32_t v[2]={[c[0]unsignedIntValue],[c[1]unsignedIntValue]};id<MTLComputeCommandEncoder>e=receptionComputeEncoder(pbuf);[e setComputePipelineState:fieldPSO];[e setBuffer:buffers[@"records"]offset:128 atIndex:0];[e setBytes:v length:8 atIndex:1];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];[e endEncoding];}
#endif
  if(split)[pbuf commit];
#if !KP_DATAFLOW_NATIVE
  if(![plan encodeCommandIRInCommandBuffer:main afterProducer:producer?pbuf:nil error:&error]){emit(@{@"failure":@"materialize",@"error":error.description?:@"nil"});return 10;}
#endif
  if(consumerPresent){id<MTLComputeCommandEncoder>e=receptionComputeEncoder(main);
#if !KP_DATAFLOW_NATIVE
   if(![NSStringFromClass(object_getClass(e))hasPrefix:@"KPICBEncoder_"])return 11;
#endif
   for(id<MTLBuffer>r in buffers.allValues)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(id<MTLBuffer>r in params)[e useResource:r usage:MTLResourceUsageRead];
   @try{if(copy){[e executeCommandsInBuffer:target withRange:NSMakeRange(first,1)];[e executeCommandsInBuffer:target withRange:NSMakeRange(first+3,1)];[e executeCommandsInBuffer:target withRange:NSMakeRange(first+1,2)];}else[e executeCommandsInBuffer:target withRange:NSMakeRange(first,3)];}@catch(NSException*x){[e endEncoding];emit(@{@"failure":@"execute",@"trial":@(trial),@"error":x.reason?:@"nil"});return 11;}[e endEncoding];}
#if !KP_DATAFLOW_NATIVE
  NSArray*targetRecords=[plan valueForKey:@"targetRecords"];for(NSUInteger k=0;k<targetRecords.count;k++){id<MTLBuffer>v=[targetRecords[k]valueForKey:@"constants"];NSString*key=[NSString stringWithFormat:@"CB1-%lu",(unsigned long)k];buffers[key]=v;hosts[key]=[d newBufferWithLength:v.length options:MTLResourceStorageModeShared];}
  id<MTLBuffer>templates=[plan valueForKey:@"constantTemplates"];buffers[@"nativeTemplates"]=templates;hosts[@"nativeTemplates"]=[d newBufferWithLength:templates.length options:MTLResourceStorageModeShared];
  id<MTLBuffer>bindingTable=[plan valueForKey:@"commandIRNativeBindings"];buffers[@"nativeBindings"]=bindingTable;hosts[@"nativeBindings"]=[d newBufferWithLength:bindingTable.length options:MTLResourceStorageModeShared];
#endif
  b=[main blitCommandEncoder];for(NSString*name in buffers){id<MTLBuffer>h=hosts[name];[b copyFromBuffer:buffers[name]sourceOffset:0 toBuffer:h destinationOffset:0 size:h.length];}if(witness)[b copyFromBuffer:witness sourceOffset:0 toBuffer:witnessHost destinationOffset:0 size:witness.length];[b endEncoding];if(!done(main))return 12;
  NSMutableDictionary*files=[NSMutableDictionary new];for(NSString*name in buffers){NSString*f=[NSString stringWithFormat:@"trial-%u-%@.bin",trial,name];id<MTLBuffer>h=hosts[name];[[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];files[name]=f;}
  if(witnessHost){NSString*f=[NSString stringWithFormat:@"trial-%u-witness.bin",trial];[[NSData dataWithBytes:witnessHost.contents length:witnessHost.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];files[@"witness"]=f;}
  NSMutableDictionary*addresses=[NSMutableDictionary new];for(NSString*k in buffers)addresses[k]=@(((id<MTLBuffer>)buffers[k]).gpuAddress);
  [runs addObject:@{@"trial":@(trial),@"specs":specs,@"buffer_bytes":@(bytes),@"files":files,@"GPU_addresses":addresses,@"rows":@(rows),@"command_status":@(main.status),@"producer_present":@(producer),@"consumer_present":@(consumerPresent),@"intermediate_CPU_waits":@0,@"events":scope?plan.events:@[],@"scope_events":scope?scope.events:@[]}];
 }}
 __weak id finalArgumentEncoder=reusableEncoder;reusableEncoder=nil;if(finalArgumentEncoder||priorArgumentPlan){emit(@{@"failure":@"reused_argument_encoder_lifetime"});return 8;}
 if(scope)[scope restore];
#if KP_FUNCTION_ARGUMENT_ENCODER && !KP_DATAFLOW_NATIVE
 MTLArgument*restoredReflection=nil;id<MTLArgumentEncoder>restoredEncoder=[producerFunction newArgumentEncoderWithBufferIndex:0 reflection:&restoredReflection];if(![NSStringFromClass(object_getClass(producerFunction))isEqual:@"_MTLFunctionInternal"]||![NSStringFromClass(object_getClass(restoredEncoder))isEqual:@"NVMTLIndirectArgumentEncoder"]||restoredEncoder.encodedLength!=48||restoredReflection.bufferDataSize!=48){emit(@{@"failure":@"native_function_restore"});return 13;}
 NSError*restoredFactoryError=nil;if([d newComputePipelineStateWithFunction:producerFunction error:&restoredFactoryError]||![restoredFactoryError.description containsString:@"air.compute_pipeline_state"])return 13;
#endif
 BOOL restored=object_getClass(d)==original;emit(@{@"mode":mode,@"native_reference":@(KP_DATAFLOW_NATIVE),@"public_argument_encoder":@(KP_PUBLIC_ARGUMENT_ENCODER),@"function_argument_encoder":@(KP_FUNCTION_ARGUMENT_ENCODER),@"native_root_binding":@YES,@"host_push_buffer_required":@NO,@"public_pipeline_factory":@YES,@"factory_kind":@(factoryKind),@"factory_evidence":factoryEvidence?:@{},@"ordinary_library_function_factories":@YES,@"manual_function_registration_calls":@0,@"library_function_evidence":receptionFunctionEvidence?:@{},@"registration_refusals_scope":@"library",@"native_control_before_library_registration":@(!KP_DATAFLOW_NATIVE),@"automatic_encoders":@YES,@"manual_compute_adaptation_calls":@0,@"queue_factory_kind":@(receptionQueueKind),@"encoder_factory_kind":@(receptionEncoderKind),@"producer_registration_refusals":@(KP_DATAFLOW_NATIVE?0:4),@"ordinary_pipeline_passthrough":@YES,@"unregistered_native_failure_preserved":@(!KP_DATAFLOW_NATIVE),@"native_factory_restored":@YES,@"function_events":scope?scope.events:@[],@"argument_refusal_probe":@(KP_ARGUMENT_REFUSALS),@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":KP_DATAFLOW_NATIVE?@{}:KPKepler880MIdentity(d),@"producer_backend":KP_DATAFLOW_NATIVE?@"apple_icb":@"NAK",@"runs":runs,@"API_refusals":@(APIrefusals),@"producer_info":info,@"producer_import":importProof,@"scope_restored":@(restored),@"CPU_expected_answers_uploaded":@NO,@"IR_CPU_read_before_execution":@NO,@"performance_benchmark":@NO,@"system_modified":@NO});return restored?0:13;
}}
