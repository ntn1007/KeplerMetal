#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#ifndef KP_NATIVE_MSL_COMMANDS
#define KP_NATIVE_MSL_COMMANDS 0
#endif
#ifndef KP_STABLE_PIPELINE_IDENTITIES
#define KP_STABLE_PIPELINE_IDENTITIES 0
#endif
#ifndef KP_REUSABLE_CONTEXTS
#define KP_REUSABLE_CONTEXTS 0
#endif
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
 BOOL reuseEncoder=[mode isEqual:@"encoder_reuse"]||KP_REUSABLE_CONTEXTS;id<MTLArgumentEncoder>reusableEncoder=nil;__weak id priorArgumentPlan=nil;
 BOOL delayedConsumer=[mode isEqual:@"delayed_consumer"],staleRoot=[mode isEqual:@"stale_root"];
 NSString*stalePlanError=nil;id<MTLIndirectCommandBuffer>persistentTarget=nil;id<MTLBuffer>previousRoot=nil;NSArray*previousResources=nil;
 BOOL duplicate=[mode isEqual:@"duplicate_templates"];
 BOOL producer=![mode isEqual:@"no_producer"],consumerPresent=![mode isEqual:@"no_consumer"],copy=[mode isEqual:@"copy"],split=[mode isEqual:@"split"],bad=[mode hasPrefix:@"bad_"];NSUInteger rows=copy?4:3,sourceCount=duplicate?6:3,slots=sourceCount+rows;
 NSString*semantic=(!producer||!consumerPresent||split||bad||delayedConsumer||staleRoot||[mode isEqual:@"encoder_reuse"]||duplicate||[mode isEqual:@"refusals"])?@"basic":mode;
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
 id<MTLLibrary>lib=load(d,[assets stringByAppendingPathComponent:@"consumer.metallib"],&error);for(NSString*n in names){MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=[lib newFunctionWithName:n];p.supportIndirectCommandBuffers=YES;id<MTLComputePipelineState>x=[d newComputePipelineStateWithDescriptor:p options:MTLPipelineOptionNone reflection:nil error:&error];if(!x)return 3;[pipelines addObject:x];}
 id<MTLLibrary>p=load(d,[assets stringByAppendingPathComponent:@"producer.metallib"],&error);producerFunction=[p newFunctionWithName:[@"encode_dataflow_" stringByAppendingString:semantic]];writer=[d newComputePipelineStateWithFunction:producerFunction error:&error];
#else
 NSData*lib=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.metallib"]],*manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.json"]];if(![hash(lib)isEqual:@"7b415aef3f5feb660698dfa0816b11a62d35da9ccc71cd83be170fabd904349f"])return 3;
 scope=[KPCPUICBScope installOnDevice:d queue:q libraryData:lib expectedSHA256:hash(lib)manifestData:manifest expectedManifestSHA256:hash(manifest)error:&error];if(!scope){emit(@{@"failure":@"register",@"error":error.description?:@"nil"});return 3;}for(NSString*n in names)[pipelines addObject:[scope pipelineForFunction:n]];
 for(NSArray*a in @[@[@"gpu_command_selector.metallib",@0],@[@"gpu_command_geometry.metallib",@1],@[@"gpu_command_bindings.metallib",@2],@[@"materializer.metallib",@3]]){NSData*b=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:a[0]]];BOOL ok=NO;switch([a[1]intValue]){case 0:ok=[scope enableGPUCommandSelectionWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 1:ok=[scope enableGPUCommandGeometryWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 2:ok=[scope enableGPUCommandBindingsWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 3:ok=[scope enableGPUCommandIRv2WithLibraryData:b expectedSHA256:hash(b)error:&error];}if(!ok){emit(@{@"failure":@"enable",@"error":error.description?:@"nil"});return 3;}}
#if KP_NATIVE_MSL_COMMANDS
 NSString*producerFile=KP_REUSABLE_CONTEXTS?@"reusable_producer.metallib":@"native_producer.metallib";
 NSData*producerData=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:producerFile]];
#if KP_FUNCTION_ARGUMENT_ENCODER
#if KP_REUSABLE_CONTEXTS
 producerFunction=[scope newReusableCommandIRFunctionWithLibraryData:producerData expectedSHA256:hash(producerData) functionName:[@"encode_dataflow_" stringByAppendingString:semantic]rootBufferIndex:0 error:&error];
#else
 producerFunction=[scope newNativeSourceCommandIRFunctionWithLibraryData:producerData expectedSHA256:hash(producerData) functionName:[@"encode_dataflow_" stringByAppendingString:semantic]rootBufferIndex:0 error:&error];
#endif
#else
 id<MTLLibrary>producerLibrary=load(d,[assets stringByAppendingPathComponent:@"native_producer.metallib"],&error);
 producerFunction=[producerLibrary newFunctionWithName:[@"encode_dataflow_" stringByAppendingString:semantic]];
#endif
 if(!producerFunction){emit(@{@"failure":@"native_producer_function",@"error":error.description?:@"nil"});return 3;}
 writer=[d newComputePipelineStateWithFunction:producerFunction error:&error];
 id<MTLArgumentEncoder>nativeArguments=[producerFunction newArgumentEncoderWithBufferIndex:0];
 if(!writer||writer.threadExecutionWidth!=32||writer.maxTotalThreadsPerThreadgroup<32||nativeArguments.encodedLength!=48||nativeArguments.alignment!=8){emit(@{@"failure":@"native_producer_contract",@"error":error.description?:@"nil",@"root_bytes":@(nativeArguments.encodedLength)});return 3;}
 info=@{@"command_ir_version":@2,@"root_bytes":@48,@"thread_width":@(writer.threadExecutionWidth),@"pipeline_class":NSStringFromClass(object_getClass(writer)),@"function":producerFunction.name,@"library_SHA256":hash(producerData),@"library_file":producerFile,@"generation_tagged_root":@(KP_REUSABLE_CONTEXTS),@"producer_backend":@"native_msl",@"instruction_import":@NO,@"Apple_ICB_layout":@NO};
 id<MTLLibrary>f=load(d,[assets stringByAppendingPathComponent:@"field.metallib"],&error);fieldPSO=[d newComputePipelineStateWithFunction:[f newFunctionWithName:@"mutate_command_ir_data"]error:&error];
#else
 info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[semantic stringByAppendingString:@".json"]]]options:0 error:nil];if([info[@"command_ir_version"]intValue]!=2||[info[@"sm"]intValue]!=30||[info[@"buffer_slots"]intValue]!=1||[info[@"push_bytes"]intValue]!=32||[info[@"grid_offset"]intValue]!=8||[info[@"scratch_bytes"]intValue]||[info[@"crs_bytes"]intValue])return 3;
 writer=KPCreatePipeline(d,[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"carrier.metallib"]],@"command_ir_carrier",[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[semantic stringByAppendingString:@".sass"]]],{[info[@"registers"]unsignedIntValue],576,576},&error,&importProof);id<MTLLibrary>f=load(d,[assets stringByAppendingPathComponent:@"field.metallib"],&error);fieldPSO=[d newComputePipelineStateWithFunction:[f newFunctionWithName:@"mutate_command_ir_data"]error:&error];
#endif
#endif
#if KP_FUNCTION_ARGUMENT_ENCODER && !KP_DATAFLOW_NATIVE && !KP_NATIVE_MSL_COMMANDS
 NSData*functionLibrary=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"producer.metallib"]];producerFunction=[scope newCommandIRFunctionWithLibraryData:functionLibrary expectedSHA256:@"a9367d4492cd100adfcde990efe0b043e4b070536a3615be5b9b2f63bfb473db" functionName:[@"encode_dataflow_" stringByAppendingString:semantic]rootBufferIndex:0 error:&error];if(!producerFunction){emit(@{@"failure":@"function_registration",@"error":error.description?:@"nil"});return 3;}
#endif
 NSMutableArray*stableIDs=[NSMutableArray new];
#if KP_STABLE_PIPELINE_IDENTITIES
 for(id<MTLComputePipelineState>p in pipelines){uint64_t identity=[scope commandIRIdentityForPipeline:p error:&error];if(!identity||error)return 3;[stableIDs addObject:@(identity)];}
 NSMutableDictionary*stableInfo=[info mutableCopy];stableInfo[@"stable_pipeline_IDs"]=stableIDs;stableInfo[@"context_version"]=KP_REUSABLE_CONTEXTS?@4:@3;info=stableInfo;
#endif
 if(!writer)return 3;unsigned sizes[4]={256,1024,4096,32768},locals[4][3]={{32,128,1024},{33,256,512},{128,33,1024},{1024,256,33}};NSUInteger APIrefusals=0;NSMutableArray*runs=[NSMutableArray new];
 for(unsigned trial=0;trial<4;trial++){@autoreleasepool{
  unsigned n=sizes[trial],maximum=0;for(unsigned k=0;k<3;k++)maximum=MAX(maximum,((n+locals[trial][k]-1)/locals[trial][k])*locals[trial][k]);NSUInteger bytes=maximum*16+512;
  NSMutableDictionary*buffers=[NSMutableDictionary new],*hosts=[NSMutableDictionary new];
  auto allocate=[&](NSString*name,NSUInteger length){id<MTLBuffer>b=[d newBufferWithLength:length options:MTLResourceStorageModePrivate],h=[d newBufferWithLength:length options:MTLResourceStorageModeShared];if(!b||!h)return false;buffers[name]=b;hosts[name]=h;memset(h.contents,0xa5,length);return true;};
  for(NSString*name in @[@"input",@"stage0",@"stage1",@"stage2",@"dummySrc"])if(!allocate(name,bytes))return 4;
  if(!allocate(@"counter",256)||!allocate(@"dummyCounter",256)||!allocate(@"records",1216))return 4;
  for(NSString*name in @[@"counter",@"dummyCounter"]){id<MTLBuffer>h=hosts[name];memset((char*)h.contents+128,0,12);}
  NSMutableArray*params=[NSMutableArray new],*specs=[NSMutableArray new];
  for(unsigned k=0;k<slots;k++){unsigned stage=k%3,seed=0x13579+trial*97+stage*101,salt=0x7654321+trial*31+stage*137;NSString*name=[NSString stringWithFormat:@"dummy%u",k];if(!allocate(name,bytes))return 4;id<MTLBuffer>p=[d newBufferWithLength:1536 options:MTLResourceStorageModeShared];if(!p)return 4;memset(p.contents,0xa5,p.length);uint32_t words[8]={n,seed,salt,stage,locals[trial][stage],0,0,0};memcpy((char*)p.contents+256,words,sizeof words);[params addObject:p];if(k<3)[specs addObject:@{@"stage":@(stage),@"count":@(n),@"seed":@(seed),@"salt":@(salt),@"local":@(words[4]),@"groups":@((n+words[4]-1)/words[4])}];}
  id<MTLCommandBuffer>init=[q commandBuffer];id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];for(NSString*name in buffers){id<MTLBuffer>h=hosts[name];[b copyFromBuffer:h sourceOffset:0 toBuffer:buffers[name]destinationOffset:0 size:h.length];}[b endEncoding];if(!done(init))return 5;
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=4;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:slots options:MTLResourceStorageModeShared];if(!icb)return 6;
  for(unsigned k=0;k<slots;k++){unsigned stage=KP_STABLE_PIPELINE_IDENTITIES&&k<sourceCount?(trial+k)%3:k%3,param=KP_STABLE_PIPELINE_IDENTITIES&&k<sourceCount?stage:k,local=locals[trial][stage];if(duplicate&&k<sourceCount&&((trial+stage)&1u)==k/3)local=local==32?64:32;id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:k];[c setComputePipelineState:pipelines[stage]];[c setKernelBuffer:buffers[[NSString stringWithFormat:@"dummy%u",k]]offset:128 atIndex:0];if(stage)[c setKernelBuffer:buffers[@"dummySrc"]offset:128 atIndex:1];[c setKernelBuffer:params[param]offset:256 atIndex:2];[c setKernelBuffer:buffers[@"dummyCounter"]offset:128 atIndex:3];[c concurrentDispatchThreadgroups:MTLSizeMake((n+local-1)/local,1,1)threadsPerThreadgroup:MTLSizeMake(local,1,1)];}
  id<MTLIndirectCommandBuffer>target=icb;NSUInteger first=sourceCount;id<MTLBuffer>root=nil,witness=nil,witnessHost=nil;KPGPUCommandSelection*plan=nil;
#if KP_DATAFLOW_NATIVE
  target=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:rows options:MTLResourceStorageModeShared];[target resetWithRange:NSMakeRange(0,rows)];first=0;id<MTLArgumentEncoder>ae=(KP_FUNCTION_ARGUMENT_ENCODER||!KP_PUBLIC_ARGUMENT_ENCODER)?[producerFunction newArgumentEncoderWithBufferIndex:0]:publicArgumentEncoder(d);if(ae.encodedLength!=48){emit(@{@"failure":@"root_stride",@"actual":@(ae.encodedLength)});return 7;}root=[d newBufferWithLength:144 options:MTLResourceStorageModeShared];
  for(unsigned stage=0;stage<3;stage++){[ae setArgumentBuffer:root offset:stage*48];[ae setIndirectCommandBuffer:target atIndex:0];[ae setComputePipelineState:pipelines[stage]atIndex:1];[ae setBuffer:buffers[[@"stage" stringByAppendingFormat:@"%u",stage]]offset:128 atIndex:2];[ae setBuffer:buffers[stage?[@"stage" stringByAppendingFormat:@"%u",stage-1]:@"input"]offset:128 atIndex:3];[ae setBuffer:params[stage]offset:256 atIndex:4];[ae setBuffer:buffers[@"counter"]offset:128 atIndex:5];}
#else
  if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots)error:&error]){emit(@{@"failure":@"prepare",@"error":error.description?:@"nil"});return 7;}
#if KP_REUSABLE_CONTEXTS
  if(!persistentTarget)persistentTarget=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:rows options:MTLResourceStorageModeShared];
  [persistentTarget resetWithRange:NSMakeRange(0,rows)];target=persistentTarget;first=0;
  for(unsigned k=0;k<rows;k++){unsigned stage=k%3,source=sourceCount+k;id<MTLIndirectComputeCommand>c=[target indirectComputeCommandAtIndex:k];[c setComputePipelineState:pipelines[stage]];[c setKernelBuffer:buffers[[NSString stringWithFormat:@"dummy%u",source]]offset:128 atIndex:0];if(stage)[c setKernelBuffer:buffers[@"dummySrc"]offset:128 atIndex:1];[c setKernelBuffer:params[source]offset:256 atIndex:2];[c setKernelBuffer:buffers[@"dummyCounter"]offset:128 atIndex:3];[c concurrentDispatchThreadgroups:MTLSizeMake((n+locals[trial][stage]-1)/locals[trial][stage],1,1)threadsPerThreadgroup:MTLSizeMake(locals[trial][stage],1,1)];}
  if(![scope prepareResidentComputeCommands:target range:NSMakeRange(0,rows)error:&error])return 7;
  stalePlanError=nil;if(reusableEncoder){id old=[(id)reusableEncoder valueForKey:@"plan"];NSError*e=nil;if(!old||[old validateCommandIRArgumentBindings:&e]||!e)return 31;stalePlanError=e.localizedDescription;}
#endif
  NSMutableArray*entries=[NSMutableArray new];for(unsigned stage=0;stage<3;stage++)[entries addObject:@{@"bindings":@[@{@"buffer":buffers[[@"stage" stringByAppendingFormat:@"%u",stage]],@"offset":@128},@{@"buffer":buffers[stage?[@"stage" stringByAppendingFormat:@"%u",stage-1]:@"input"],@"offset":@128},@{@"buffer":buffers[@"counter"],@"offset":@128}]}];
  auto makePlan=[&](NSArray*catalogue,id<MTLBuffer>records,NSUInteger off)->KPGPUCommandSelection*{
#if KP_REUSABLE_CONTEXTS
   return[scope newGPUReusableCommandIRFromBuffer:icb sourceRange:NSMakeRange(0,sourceCount)destination:target destinationRange:NSMakeRange(0,rows)resources:catalogue records:records recordOffset:off error:&error];
#elif KP_STABLE_PIPELINE_IDENTITIES
   return[scope newGPUStableCommandIRFromBuffer:icb sourceRange:NSMakeRange(0,sourceCount)destination:icb destinationRange:NSMakeRange(sourceCount,rows)resources:catalogue records:records recordOffset:off error:&error];
#else
   return[scope newGPUCommandIRv2FromBuffer:icb sourceRange:NSMakeRange(0,sourceCount)destination:icb destinationRange:NSMakeRange(sourceCount,rows)resources:catalogue records:records recordOffset:off error:&error];
#endif
  };
  if(trial==0&&[mode isEqual:@"refusals"]){
   id command=[icb indirectComputeCommandAtIndex:0];id native=[command valueForKey:@"record"];
   for(NSString*test in @[@"duplicate_entry",@"intra_entry_alias",@"partial_overlap",@"descriptor_records_alias",@"original_binding_alias",@"unaligned",@"undersized",@"wrong_entry_type"]){NSArray*catalogue=entries;id<MTLBuffer>records=buffers[@"records"];NSUInteger off=128;
    if([test isEqual:@"duplicate_entry"])catalogue=@[entries[0],entries[0]];
    else if([test isEqual:@"descriptor_records_alias"]){records=[native valueForKey:@"descriptor"];off=0;}
    else if([test isEqual:@"wrong_entry_type"])catalogue=@[NSNull.null];
    else{NSMutableArray*e=[entries mutableCopy],*bindings=[entries[[test isEqual:@"partial_overlap"]?1:0][@"bindings"]mutableCopy];NSUInteger slot=[test isEqual:@"partial_overlap"]?2:0;NSMutableDictionary*v=[bindings[slot]mutableCopy];if([test isEqual:@"intra_entry_alias"])v[@"buffer"]=bindings[1][@"buffer"];if([test isEqual:@"partial_overlap"])v[@"offset"]=@132;if([test isEqual:@"original_binding_alias"])v[@"buffer"]=buffers[@"dummy0"];if([test isEqual:@"unaligned"])v[@"offset"]=@129;if([test isEqual:@"undersized"]){v[@"buffer"]=[d newBufferWithLength:16 options:MTLResourceStorageModePrivate];v[@"offset"]=@0;}bindings[slot]=v;e[[test isEqual:@"partial_overlap"]?1:0]=@{@"bindings":bindings};catalogue=e;}
    error=nil;id invalid=makePlan(catalogue,records,off);if(invalid||!error){emit(@{@"failure":@"API_refusal",@"case":test});return 21;}APIrefusals++;
   }
  }
  error=nil;plan=makePlan(entries,buffers[@"records"],128);if(!plan){emit(@{@"failure":@"plan",@"error":error.description?:@"nil"});return 8;}
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
  id<MTLCommandBuffer>main=[q commandBuffer],pbuf=split?[q commandBuffer]:main;
  NSMutableArray*leaseChecks=[NSMutableArray new];
#if KP_REUSABLE_CONTEXTS
  auto busyCheck=[&](NSString*phase){NSError*blocked=nil;id next=[scope newGPUReusableCommandIRFromBuffer:icb sourceRange:NSMakeRange(0,sourceCount)destination:target destinationRange:NSMakeRange(0,rows)resources:entries records:buffers[@"records"]recordOffset:128 error:&blocked];BOOL resetBlocked=NO;NSString*resetError=nil;@try{[target resetWithRange:NSMakeRange(0,rows)];}@catch(NSException*x){resetError=x.reason;resetBlocked=[x.reason containsString:@"uncompleted"];}BOOL ok=!next&&[blocked.localizedDescription containsString:@"uncompleted"]&&resetBlocked;[leaseChecks addObject:@{@"phase":phase,@"PASS":@(ok),@"prepare_refused":@(!next),@"prepare_error":blocked.localizedDescription?:@"",@"reset_refused":@(resetBlocked),@"reset_error":resetError?:@"",@"materializer_status":@(((id<MTLCommandBuffer>)[plan valueForKey:@"selectionBuffer"]).status)}];return ok;};
  if(producer&&![plan reserveCommandIRProducerInCommandBuffer:pbuf error:&error]){emit(@{@"failure":@"reserve",@"error":error.description?:@""});return 32;}
  if(producer&&!busyCheck(@"producer_reserved"))return 33;
#endif
  if(producer){id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];[e setComputePipelineState:writer];
#if KP_DATAFLOW_NATIVE
   [e setBuffer:root offset:0 atIndex:0];[e useResource:target usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(id<MTLBuffer>r in buffers.allValues)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(id<MTLBuffer>r in params)[e useResource:r usage:MTLResourceUsageRead];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];
#else
#if KP_NATIVE_MSL_COMMANDS
   id<MTLBuffer>executionRoot=KP_REUSABLE_CONTEXTS&&staleRoot&&trial?previousRoot:root;
   [e setBuffer:executionRoot offset:0 atIndex:0];
   for(id<MTLBuffer>r in plan.commandIRProducerResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];
   if(KP_REUSABLE_CONTEXTS&&staleRoot&&trial){[e useResource:previousRoot usage:MTLResourceUsageRead];for(id<MTLBuffer>r in previousResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];}
   [e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];
   NSArray*keep=KP_REUSABLE_CONTEXTS&&staleRoot&&trial?@[root,writer,plan.commandIRProducerResources,previousRoot,previousResources]:@[root,writer,plan.commandIRProducerResources];[pbuf addCompletedHandler:^(id<MTLCommandBuffer>c){(void)keep.count;}];
#else
   Push push={root.gpuAddress,{32,1,1},{32,1,1}};id<MTLBuffer>p=[d newBufferWithBytes:&push length:sizeof push options:MTLResourceStorageModeShared];[e setBuffer:p offset:0 atIndex:0];[e setBuffer:buffers[@"records"]offset:128 atIndex:1];[e useResource:root usage:MTLResourceUsageRead];for(id<MTLBuffer>r in plan.commandIRProducerResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];NSArray*keep=@[root,p,writer,plan.commandIRProducerResources];[pbuf addCompletedHandler:^(id<MTLCommandBuffer>c){(void)keep.count;}];
#endif
#endif
   [e endEncoding];}
#if !KP_DATAFLOW_NATIVE
  if(bad){NSDictionary*changes=@{@"bad_parameters":@[@16,@1],@"bad_counter":@[@26,@1],@"bad_pipeline":@[@2,@8],@"bad_buffer3_flag":@[@1,@115],@"bad_groups":@[@4,@0],@"bad_reserved":@[@28,@1]};NSArray*c=changes[mode];if(!c)return 9;uint32_t v[2]={[c[0]unsignedIntValue],[c[1]unsignedIntValue]};id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];[e setComputePipelineState:fieldPSO];[e setBuffer:buffers[@"records"]offset:128 atIndex:0];[e setBytes:v length:8 atIndex:1];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];[e endEncoding];}
#endif
  if(split)[pbuf commit];
#if !KP_DATAFLOW_NATIVE
  if(![plan encodeCommandIRInCommandBuffer:main afterProducer:producer?pbuf:nil error:&error]){emit(@{@"failure":@"materialize",@"error":error.description?:@"nil"});return 10;}
#endif
#if KP_REUSABLE_CONTEXTS
  if(!busyCheck(@"materializer_recording"))return 33;
  if(delayedConsumer){if(!done(main))return 34;main=[q commandBuffer];}
#endif
  if(consumerPresent){id<MTLComputeCommandEncoder>e=[main computeCommandEncoder];
#if !KP_DATAFLOW_NATIVE
   if(![scope adaptComputeEncoder:e error:&error])return 11;
#endif
   for(id<MTLBuffer>r in buffers.allValues)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(id<MTLBuffer>r in params)[e useResource:r usage:MTLResourceUsageRead];
   @try{if(copy){[e executeCommandsInBuffer:target withRange:NSMakeRange(first,1)];[e executeCommandsInBuffer:target withRange:NSMakeRange(first+3,1)];[e executeCommandsInBuffer:target withRange:NSMakeRange(first+1,2)];}else[e executeCommandsInBuffer:target withRange:NSMakeRange(first,3)];}@catch(NSException*x){[e endEncoding];emit(@{@"failure":@"execute",@"trial":@(trial),@"error":x.reason?:@"nil"});return 11;}[e endEncoding];}
#if KP_REUSABLE_CONTEXTS
  if(consumerPresent&&!busyCheck(delayedConsumer?@"consumer_after_completed_materializer":@"consumer_recording"))return 33;
#endif
#if !KP_DATAFLOW_NATIVE
  NSArray*targetRecords=[plan valueForKey:@"targetRecords"];for(NSUInteger k=0;k<targetRecords.count;k++){id<MTLBuffer>v=[targetRecords[k]valueForKey:@"constants"];NSString*key=[NSString stringWithFormat:@"CB1-%lu",(unsigned long)k];buffers[key]=v;hosts[key]=[d newBufferWithLength:v.length options:MTLResourceStorageModeShared];}
  id<MTLBuffer>templates=[plan valueForKey:@"constantTemplates"];buffers[@"nativeTemplates"]=templates;hosts[@"nativeTemplates"]=[d newBufferWithLength:templates.length options:MTLResourceStorageModeShared];
  id<MTLBuffer>bindingTable=[plan valueForKey:@"commandIRNativeBindings"];buffers[@"nativeBindings"]=bindingTable;hosts[@"nativeBindings"]=[d newBufferWithLength:bindingTable.length options:MTLResourceStorageModeShared];
#if KP_STABLE_PIPELINE_IDENTITIES
  id<MTLBuffer>context=[plan valueForKey:@"commandIRContext"];buffers[@"producerContext"]=context;hosts[@"producerContext"]=[d newBufferWithLength:context.length options:MTLResourceStorageModeShared];
#endif
#endif
  b=[main blitCommandEncoder];for(NSString*name in buffers){id<MTLBuffer>h=hosts[name];[b copyFromBuffer:buffers[name]sourceOffset:0 toBuffer:h destinationOffset:0 size:h.length];}if(witness)[b copyFromBuffer:witness sourceOffset:0 toBuffer:witnessHost destinationOffset:0 size:witness.length];[b endEncoding];if(!done(main))return 12;
  NSMutableDictionary*files=[NSMutableDictionary new];for(NSString*name in buffers){NSString*f=[NSString stringWithFormat:@"trial-%u-%@.bin",trial,name];id<MTLBuffer>h=hosts[name];[[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];files[name]=f;}
  if(witnessHost){NSString*f=[NSString stringWithFormat:@"trial-%u-witness.bin",trial];[[NSData dataWithBytes:witnessHost.contents length:witnessHost.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];files[@"witness"]=f;}
  NSMutableDictionary*addresses=[NSMutableDictionary new];for(NSString*k in buffers)addresses[k]=@(((id<MTLBuffer>)buffers[k]).gpuAddress);
  NSMutableDictionary*trialInfo=[@{@"trial":@(trial),@"specs":specs,@"buffer_bytes":@(bytes),@"files":files,@"GPU_addresses":addresses,@"rows":@(rows),@"command_status":@(main.status),@"producer_present":@(producer),@"consumer_present":@(consumerPresent),@"intermediate_CPU_waits":@0,@"events":scope?plan.events:@[],@"scope_events":scope?scope.events:@[]}mutableCopy];
#if KP_STABLE_PIPELINE_IDENTITIES
  NSString*rootFile=[NSString stringWithFormat:@"trial-%u-roots.bin",trial];[[NSData dataWithBytes:root.contents length:144]writeToFile:[out stringByAppendingPathComponent:rootFile]atomically:YES];trialInfo[@"root_file"]=rootFile;
  NSMutableArray*currentIDs=[NSMutableArray new];for(id<MTLComputePipelineState>p in pipelines){error=nil;uint64_t identity=[scope commandIRIdentityForPipeline:p error:&error];if(error||!identity)return 12;[currentIDs addObject:@(identity)];}trialInfo[@"queried_pipeline_IDs"]=currentIDs;
#endif
#if KP_REUSABLE_CONTEXTS
  trialInfo[@"stale_plan_error"]=stalePlanError?:@"";trialInfo[@"generation"]=[plan valueForKey:@"reusableGeneration"];trialInfo[@"lease_checks"]=leaseChecks;trialInfo[@"intermediate_CPU_waits"]=delayedConsumer?@1:@0;
  if(staleRoot&&trial){NSString*f=[NSString stringWithFormat:@"trial-%u-stale-roots.bin",trial];[[NSData dataWithBytes:previousRoot.contents length:144]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];trialInfo[@"stale_root_file"]=f;}
  // A rejected direct mutation must not detach a retired slot from its lease.
  NSString*mutationError=nil,*retiredConsumerError=nil;@try{[[target indirectComputeCommandAtIndex:0]setComputePipelineState:pipelines[0]];}@catch(NSException*x){mutationError=x.reason;}
  id<MTLCommandBuffer>retiredCB=[q commandBuffer];id<MTLComputeCommandEncoder>retiredEncoder=[retiredCB computeCommandEncoder];if(![scope adaptComputeEncoder:retiredEncoder error:&error])return 35;
  @try{[retiredEncoder executeCommandsInBuffer:target withRange:NSMakeRange(0,1)];}@catch(NSException*x){retiredConsumerError=x.reason;}[retiredEncoder endEncoding];
  if(![mutationError containsString:@"requires reset"]||![retiredConsumerError containsString:@"not materialized/active"]){emit(@{@"failure":@"retired_slot_detached",@"mutation":mutationError?:@"",@"consumer":retiredConsumerError?:@""});return 35;}
  trialInfo[@"retired_mutation_error"]=mutationError;trialInfo[@"retired_consumer_error"]=retiredConsumerError;
  previousRoot=root;previousResources=plan.commandIRProducerResources;
#endif
  [runs addObject:trialInfo];
 }}
 __weak id finalArgumentEncoder=reusableEncoder;reusableEncoder=nil;if(finalArgumentEncoder||priorArgumentPlan){emit(@{@"failure":@"reused_argument_encoder_lifetime"});return 8;}
 if(scope)[scope restore];
#if KP_FUNCTION_ARGUMENT_ENCODER && !KP_DATAFLOW_NATIVE
 MTLArgument*restoredReflection=nil;id<MTLArgumentEncoder>restoredEncoder=[producerFunction newArgumentEncoderWithBufferIndex:0 reflection:&restoredReflection];if(![NSStringFromClass(object_getClass(producerFunction))isEqual:@"_MTLFunctionInternal"]||![NSStringFromClass(object_getClass(restoredEncoder))isEqual:@"NVMTLIndirectArgumentEncoder"]||restoredEncoder.encodedLength!=48||restoredReflection.bufferDataSize!=48){emit(@{@"failure":@"native_function_restore"});return 13;}
#endif
 BOOL restored=object_getClass(d)==original;emit(@{@"mode":mode,@"native_reference":@(KP_DATAFLOW_NATIVE),@"public_argument_encoder":@(KP_PUBLIC_ARGUMENT_ENCODER),@"function_argument_encoder":@(KP_FUNCTION_ARGUMENT_ENCODER),@"function_events":scope?scope.events:@[],@"argument_refusal_probe":@(KP_ARGUMENT_REFUSALS),@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":KP_DATAFLOW_NATIVE?@{}:KPKepler880MIdentity(d),@"producer_backend":KP_NATIVE_MSL_COMMANDS?@"native_msl":(KP_DATAFLOW_NATIVE?@"apple_icb":@"NAK"),@"runs":runs,@"API_refusals":@(APIrefusals),@"producer_info":info,@"producer_import":importProof,@"scope_restored":@(restored),@"CPU_expected_answers_uploaded":@NO,@"IR_CPU_read_before_execution":@NO,@"performance_benchmark":@NO,@"system_modified":@NO});return restored?0:13;
}}
