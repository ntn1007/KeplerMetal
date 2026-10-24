// Explicit reusable-context leases. No cancellation of an uncommitted buffer:
// it could still be committed later. Only successful completion permits reuse.
@interface KPReusableIRContext : NSObject
@property(nonatomic,strong) id<MTLBuffer> buffer;
@property(nonatomic,strong) id<MTLCommandQueue> queue;
@property(nonatomic,strong) NSThread *ownerThread;
@property(nonatomic,strong) NSMutableDictionary *pending;
@property(nonatomic,strong) NSArray *resources;
@property(nonatomic,weak) KPGPUCommandSelection *plan;
@property(nonatomic) uint32_t generation;
@property(nonatomic) BOOL retired,preparing,poisoned;
- (BOOL)idle:(NSError**)error;
- (BOOL)track:(id<MTLCommandBuffer>)buffer generation:(uint32_t)generation error:(NSError**)error;
- (BOOL)retire:(NSError**)error;
@end
@implementation KPReusableIRContext
- (instancetype)init{if((self=[super init])){_pending=[NSMutableDictionary new];_ownerThread=NSThread.currentThread;_retired=YES;}return self;}
- (BOOL)idle:(NSError**)error{
 @synchronized(self){
  if(NSThread.currentThread!=_ownerThread)return fail(error,@"Reusable context owner thread differs");
  for(NSValue*key in [_pending.allKeys copy]){id<MTLCommandBuffer>b=_pending[key];if(b.status==MTLCommandBufferStatusError){_poisoned=YES;[_pending removeObjectForKey:key];}else if(b.status==MTLCommandBufferStatusCompleted)[_pending removeObjectForKey:key];}
  if(_poisoned)return fail(error,@"Reusable context is poisoned by a command error");
  if(_preparing||_pending.count)return fail(error,@"Reusable context still has uncompleted submissions");
  return YES;
 }
}
- (BOOL)retire:(NSError**)error{
 @synchronized(self){if(![self idle:error])return NO;_retired=YES;_plan=nil;return YES;}
}
- (BOOL)track:(id<MTLCommandBuffer>)buffer generation:(uint32_t)generation error:(NSError**)error{
 @synchronized(self){
  if(NSThread.currentThread!=_ownerThread||_retired||_poisoned||_preparing||generation!=_generation||!generation)return fail(error,@"Reusable context generation is inactive");
  if(!buffer||buffer.commandQueue!=_queue||buffer.status!=MTLCommandBufferStatusNotEnqueued||!buffer.retainedReferences)return fail(error,@"Reusable context requires a retained recording buffer from its queue");
  NSValue*key=[NSValue valueWithPointer:(__bridge const void*)buffer];if(_pending[key])return YES;
  _pending[key]=buffer;KPReusableIRContext*lease=self;
  [buffer addCompletedHandler:^(id<MTLCommandBuffer>done){@synchronized(lease){if(done.status==MTLCommandBufferStatusError)lease.poisoned=YES;if(lease.pending[key]==done)[lease.pending removeObjectForKey:key];}}];
  return YES;
 }
}
@end
