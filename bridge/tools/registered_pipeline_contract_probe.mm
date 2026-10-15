#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <pthread.h>
#include <initializer_list>
#ifndef KP_PIPELINE_NEGATIVE_TESTS
#define KP_PIPELINE_NEGATIVE_TESTS 0
#endif
@interface KPCommandIRProducerFactory : NSObject
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device carrier:(NSData*)carrier program:(NSData*)program descriptor:(MTLComputePipelineDescriptor*)descriptor error:(NSError**)error evidence:(NSDictionary**)evidence;
@end
static NSString*hash(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(auto x:h)[s appendFormat:@"%02x",x];return s;}
static BOOL reflectionOK(MTLComputePipelineReflection*r){
 if(!r||r.arguments.count!=1||r.bindings.count!=1)return NO;MTLArgument*a=r.arguments[0];id<MTLBufferBinding>b=(id)r.bindings[0];
 if(a.index||a.bufferDataSize!=48||a.bufferAlignment!=8||a.bufferStructType.members.count!=6||b.type!=MTLBindingTypeBuffer||b.index||b.bufferDataSize!=48||b.bufferStructType!=a.bufferStructType)return NO;
 for(NSUInteger i=0;i<6;i++){MTLStructMember*m=a.bufferStructType.members[i];if(m.offset!=8*i||m.argumentIndex!=i||m.dataType!=(i==0?MTLDataTypeIndirectCommandBuffer:i==1?MTLDataTypeComputePipeline:MTLDataTypePointer))return NO;}return YES;
}
@interface KPContractReply : NSObject
@property(nonatomic,strong) NSLock*lock;
@property(nonatomic) NSUInteger count;
@property(nonatomic,strong) id<MTLComputePipelineState>pipeline;
@property(nonatomic,strong) MTLComputePipelineReflection*reflection;
@property(nonatomic,strong) NSError*error;
@property(nonatomic) BOOL otherThread;
@end
@implementation KPContractReply
@end
#include "PipelineContractPendingReply.inc"
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]);id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;Class original=object_getClass(d);NSMutableArray*runs=[NSMutableArray new];MTLComputePipelineDescriptor*defaults=[MTLComputePipelineDescriptor new];NSDictionary*descriptorDefaults=@{@"stage_input":@(defaults.stageInputDescriptor!=nil),@"indirect":@(defaults.supportIndirectCommandBuffers),@"adding_binary":@(defaults.supportAddingBinaryFunctions),@"max_call_stack":@(defaults.maxCallStackDepth),@"shader_validation":([defaults respondsToSelector:@selector(shaderValidation)]?@(defaults.shaderValidation):@"selector_unavailable"),@"preloaded":([defaults respondsToSelector:@selector(preloadedLibraries)]?@(defaults.preloadedLibraries.count):@"selector_unavailable"),@"insert":@(defaults.insertLibraries.count),@"archives":@(defaults.binaryArchives.count)};KPContractReply*pendingReply=nil;dispatch_semaphore_t pendingDone=nil;Method pendingMethod=nullptr;BOOL pendingObserved=NO;__weak KPCPUICBScope*weakScope=nil;MTLComputePipelineReflection*survivingReflection=nil;
 @autoreleasepool{
  NSError*error=nil;id<MTLCommandQueue>q=[d newCommandQueue];NSData*consumer=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.metallib"]],*manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.json"]];KPCPUICBScope*s=[KPCPUICBScope installOnDevice:d queue:q libraryData:consumer expectedSHA256:hash(consumer)manifestData:manifest expectedManifestSHA256:hash(manifest)error:&error];if(!s)return 3;weakScope=s;
  for(NSArray*a in @[@[@"gpu_command_selector.metallib",@0],@[@"gpu_command_geometry.metallib",@1],@[@"gpu_command_bindings.metallib",@2],@[@"materializer.metallib",@3]]){NSData*b=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:a[0]]];BOOL ok=NO;switch([a[1]intValue]){case 0:ok=[s enableGPUCommandSelectionWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 1:ok=[s enableGPUCommandGeometryWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 2:ok=[s enableGPUCommandBindingsWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 3:ok=[s enableGPUCommandIRv2WithLibraryData:b expectedSHA256:hash(b)error:&error];}if(!ok)return 3;}
  NSData*producer=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"producer.metallib"]],*carrier=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"carrier.metallib"]],*code=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"basic.sass"]];id<MTLFunction>f=[s newCommandIRFunctionWithLibraryData:producer expectedSHA256:hash(producer)functionName:@"encode_dataflow_basic" rootBufferIndex:0 error:&error];if(!f||![s registerCommandIRProducerForFunction:f carrierData:carrier programData:code error:&error])return 4;
  MTLComputePipelineDescriptor*diag=[MTLComputePipelineDescriptor new];diag.computeFunction=f;diag.label=@"native-diagnostic";diag.maxTotalThreadsPerThreadgroup=32;diag.threadGroupSizeIsMultipleOfThreadExecutionWidth=YES;NSDictionary*diagProof=nil;NSError*diagError=nil;id<MTLComputePipelineState>diagPipeline=[KPCommandIRProducerFactory newPipelineForDevice:d carrier:carrier program:code descriptor:diag error:&diagError evidence:&diagProof];
  descriptorDefaults=[descriptorDefaults mutableCopy];[(NSMutableDictionary*)descriptorDefaults setObject:@{@"pipeline":@(diagPipeline!=nil),@"max_threads":@(diagPipeline?diagPipeline.maxTotalThreadsPerThreadgroup:0),@"label":diagPipeline.label?:@"",@"width":@(diagPipeline?diagPipeline.threadExecutionWidth:0),@"proof":diagProof?:@{},@"error":diagError.description?:@""}forKey:@"native_descriptor_diagnostic"];
  for(NSString*kind in @[@"function",@"descriptor",@"async_function",@"async_options",@"async_descriptor"]){
   unsigned limit=[kind isEqual:@"async_function"]?1:4;
   for(unsigned options=0;options<limit;options++){
    MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=f;p.label=[NSString stringWithFormat:@"contract-%@-%u",kind,options];p.maxTotalThreadsPerThreadgroup=0;p.threadGroupSizeIsMultipleOfThreadExecutionWidth=YES;
    id<MTLComputePipelineState>pipeline=nil;MTLComputePipelineReflection*reflection=nil;error=nil;BOOL offThread=NO;NSUInteger callbacks=0;
    if([kind isEqual:@"function"])pipeline=[d newComputePipelineStateWithFunction:f options:options reflection:&reflection error:&error];
    else if([kind isEqual:@"descriptor"])pipeline=[d newComputePipelineStateWithDescriptor:p options:options reflection:&reflection error:&error];
    else{
     dispatch_semaphore_t sem=dispatch_semaphore_create(0);KPContractReply*reply=[KPContractReply new];reply.lock=[NSLock new];pthread_t caller=pthread_self();
     void(^complete)(id<MTLComputePipelineState>,MTLComputePipelineReflection*,NSError*)=^(id<MTLComputePipelineState>x,MTLComputePipelineReflection*y,NSError*z){[reply.lock lock];reply.count++;reply.pipeline=x;reply.reflection=y;reply.error=z;reply.otherThread=!pthread_equal(caller,pthread_self());[reply.lock unlock];dispatch_semaphore_signal(sem);};
     if([kind isEqual:@"async_function"])[d newComputePipelineStateWithFunction:f completionHandler:^(id<MTLComputePipelineState>x,NSError*e){complete(x,nil,e);}];
     else if([kind isEqual:@"async_options"])[d newComputePipelineStateWithFunction:f options:options completionHandler:complete];
     else [d newComputePipelineStateWithDescriptor:p options:options completionHandler:complete];
     p.label=@"mutated-after-call";p.maxTotalThreadsPerThreadgroup=16;
     if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return 5;
     [reply.lock lock];pipeline=reply.pipeline;reflection=reply.reflection;error=reply.error;offThread=reply.otherThread;callbacks=reply.count;[reply.lock unlock];if(callbacks!=1||!offThread)return 6;
    }
    BOOL descriptor=[kind containsString:@"descriptor"];NSString*wanted=[NSString stringWithFormat:@"contract-%@-%u",kind,options];BOOL ok=pipeline&&!error&&(options?reflectionOK(reflection):!reflection)&&(!descriptor||([pipeline.label isEqual:wanted]&&pipeline.maxTotalThreadsPerThreadgroup<=1024));
    NSDictionary*proof=pipeline?objc_getAssociatedObject(pipeline,sel_registerName("KeplerMetalProducerEvidence-v1")):nil;ok=ok&&[proof[@"contract_verified"]boolValue];
    [runs addObject:@{@"kind":kind,@"options":@(options),@"PASS":@(ok),@"error":error.description?:@"",@"pipeline":@(pipeline!=nil),@"requested_max_threads":@0,@"max_threads":@(pipeline?pipeline.maxTotalThreadsPerThreadgroup:0),@"label":pipeline.label?:@"",@"reflection_class":reflection?NSStringFromClass(object_getClass(reflection)):@"",@"callbacks":@(callbacks),@"off_thread":@(offThread),@"native_import_verified":@([proof[@"contract_verified"]boolValue])}];
    if(reflection)survivingReflection=reflection;
   }
  }
#if KP_PIPELINE_NEGATIVE_TESTS
#include "PipelineContractNegativeCases.inc"
#endif

  if([@(argv[3])isEqual:@"pending"]){
   pendingEntered=dispatch_semaphore_create(0);pendingResume=dispatch_semaphore_create(0);pendingDone=dispatch_semaphore_create(0);pendingReply=[KPContractReply new];pendingReply.lock=[NSLock new];KPContractReply*reply=pendingReply;dispatch_semaphore_t done=pendingDone;
   pendingMethod=class_getClassMethod(NSClassFromString(@"KPCommandIRProducerFactory"),@selector(newPipelineForDevice:carrier:program:descriptor:error:evidence:));if(!pendingMethod)return 10;pendingOriginal=method_setImplementation(pendingMethod,(IMP)pausedOwnFactory);
   MTLComputePipelineDescriptor*request=[MTLComputePipelineDescriptor new];request.computeFunction=f;request.label=@"survive-scope";
   [d newComputePipelineStateWithDescriptor:request options:MTLPipelineOption(3)completionHandler:^(id<MTLComputePipelineState>x,MTLComputePipelineReflection*y,NSError*z){[reply.lock lock];reply.count++;reply.pipeline=x;reply.reflection=y;reply.error=z;[reply.lock unlock];dispatch_semaphore_signal(done);}];
   if(dispatch_semaphore_wait(pendingEntered,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC))){dispatch_semaphore_signal(pendingResume);method_setImplementation(pendingMethod,pendingOriginal);return 10;}
   pendingObserved=YES;[s restore];s=nil;
  }
 }

 if(pendingObserved){
  BOOL releasedWhilePending=!weakScope&&object_getClass(d)==original;
  [pendingReply.lock lock];NSUInteger early=pendingReply.count;[pendingReply.lock unlock];
  dispatch_semaphore_signal(pendingResume);
  BOOL ended=!dispatch_semaphore_wait(pendingDone,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC));method_setImplementation(pendingMethod,pendingOriginal);
  [pendingReply.lock lock];BOOL passed=releasedWhilePending&&early==0&&ended&&pendingReply.count==1&&pendingReply.pipeline&&!pendingReply.error&&reflectionOK(pendingReply.reflection)&&[pendingReply.pipeline.label isEqual:@"survive-scope"];[pendingReply.lock unlock];
  [runs addObject:@{@"kind":@"pending_scope_release",@"PASS":@(passed),@"request_observed_before_release":@YES,@"scope_released_before_callback":@(releasedWhilePending),@"early_callbacks":@(early),@"factory_method_restored":@(method_getImplementation(pendingMethod)==pendingOriginal),@"user_kernel_submitted":@NO}];
 }
 BOOL released=!weakScope&&object_getClass(d)==original&&reflectionOK(survivingReflection);
 NSDictionary*v=@{@"device":d.name,@"runs":runs,@"scope_released_with_reflection_alive":@(released),@"descriptor_defaults":descriptorDefaults,@"command_buffers_submitted":@NO,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:v options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return released?0:7;
}}
