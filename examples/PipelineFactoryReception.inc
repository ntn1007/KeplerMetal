// Shared by GTX and native M1 reception clients. No private native API calls.
#include <pthread.h>
@interface KPFactoryReply : NSObject
@property(nonatomic,strong) NSLock*lock;
@property(nonatomic) NSUInteger count;
@property(nonatomic,strong) id<MTLComputePipelineState>pipeline;
@property(nonatomic,strong) MTLComputePipelineReflection*reflection;
@property(nonatomic,strong) NSError*error;
@property(nonatomic) BOOL offThread;
@end
@implementation KPFactoryReply
@end
static id<MTLComputePipelineState>receptionPipeline(id<MTLDevice>d,id<MTLFunction>f,NSUInteger kind,NSDictionary**details,NSError**error){
 id<MTLComputePipelineState>pipeline=nil;MTLComputePipelineReflection*reflection=nil;NSUInteger callbacks=0;BOOL offThread=NO;
 MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=f;p.label=[@"reception-" stringByAppendingString:f.name];p.maxTotalThreadsPerThreadgroup=0;p.threadGroupSizeIsMultipleOfThreadExecutionWidth=YES;NSString*wanted=[p.label copy];
 if(kind==0)pipeline=[d newComputePipelineStateWithFunction:f error:error];
 else if(kind==1)pipeline=[d newComputePipelineStateWithFunction:f options:MTLPipelineOption(3)reflection:&reflection error:error];
 else if(kind==2)pipeline=[d newComputePipelineStateWithDescriptor:p options:MTLPipelineOption(3)reflection:&reflection error:error];
 else{
  KPFactoryReply*reply=[KPFactoryReply new];reply.lock=[NSLock new];pthread_t caller=pthread_self();dispatch_semaphore_t sem=dispatch_semaphore_create(0);
  void(^complete)(id<MTLComputePipelineState>,MTLComputePipelineReflection*,NSError*)=^(id<MTLComputePipelineState>x,MTLComputePipelineReflection*y,NSError*z){[reply.lock lock];reply.count++;reply.pipeline=x;reply.reflection=y;reply.error=z;reply.offThread=!pthread_equal(caller,pthread_self());[reply.lock unlock];dispatch_semaphore_signal(sem);};
  if(kind==3)[d newComputePipelineStateWithFunction:f completionHandler:^(id<MTLComputePipelineState>x,NSError*e){complete(x,nil,e);}];
  else if(kind==4)[d newComputePipelineStateWithFunction:f options:MTLPipelineOption(3)completionHandler:complete];
  else if(kind==5)[d newComputePipelineStateWithDescriptor:p options:MTLPipelineOption(3)completionHandler:complete];
  else return nil;
  if(kind==5){p.label=@"mutated-after-call";p.maxTotalThreadsPerThreadgroup=16;}
  if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return nil;
  [reply.lock lock];pipeline=reply.pipeline;reflection=reply.reflection;if(error)*error=reply.error;callbacks=reply.count;offThread=reply.offThread;[reply.lock unlock];if(callbacks!=1)return nil;
 }
 if(!pipeline)return nil;
 BOOL wantsReflection=kind==1||kind==2||kind==4||kind==5;
 NSMutableArray*members=[NSMutableArray new];
 if(wantsReflection){
  if(reflection.arguments.count!=1||reflection.bindings.count!=1)return nil;MTLArgument*a=reflection.arguments[0];id<MTLBufferBinding>b=(id)reflection.bindings[0];
  if(a.index||a.bufferDataSize!=48||a.bufferAlignment!=8||a.bufferStructType.members.count!=6||b.type!=MTLBindingTypeBuffer||b.index||b.bufferDataSize!=48||b.bufferAlignment!=8)return nil;
  for(NSUInteger i=0;i<6;i++){MTLStructMember*m=a.bufferStructType.members[i];if(m.offset!=i*8||m.argumentIndex!=i||m.dataType!=(i==0?MTLDataTypeIndirectCommandBuffer:i==1?MTLDataTypeComputePipeline:MTLDataTypePointer))return nil;[members addObject:@{@"index":@(m.argumentIndex),@"offset":@(m.offset),@"type":@(m.dataType)}];}
 }
 if((kind==2||kind==5)&&(![pipeline.label isEqual:wanted]||pipeline.maxTotalThreadsPerThreadgroup>1024))return nil;
 if(details)*details=@{@"kind":@(kind),@"callbacks":@(callbacks),@"off_thread":@(offThread),@"reflection":@(reflection!=nil),@"reflection_class":reflection?NSStringFromClass(object_getClass(reflection)):@"",@"members":members,@"requested_max_threads":@0,@"max_threads":@(pipeline.maxTotalThreadsPerThreadgroup),@"label":pipeline.label?:@"",@"descriptor_mutation_ignored":@(kind==5)};
 return pipeline;
}
