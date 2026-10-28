// Explicit reusable-context leases. Only a cooperatively owned, single-plan
// producer can use the experimental instance-local abandonment path.
#import <objc/runtime.h>
#include <cstring>
static char KPReusableOwnerKey;
static NSHashTable* KPReusableOwners(id buffer,BOOL create){
 NSHashTable*owners=objc_getAssociatedObject(buffer,&KPReusableOwnerKey);
 if(!owners&&create){owners=[NSHashTable weakObjectsHashTable];objc_setAssociatedObject(buffer,&KPReusableOwnerKey,owners,OBJC_ASSOCIATION_RETAIN_NONATOMIC);}return owners;
}
static void KPReusableUnregister(id buffer,id owner){@autoreleasepool{@synchronized(buffer){[KPReusableOwners(buffer,NO)removeObject:owner];}}}
static void KPReusableRevoked(id,SEL s){[NSException raise:@"KeplerAbandonedCommandBuffer" format:@"%@ is unavailable after explicit producer abandonment",NSStringFromSelector(s)];}
static Class KPReusableRevokedClass(){
 static Class result=Nil;static dispatch_once_t once;dispatch_once(&once,^{
  Class base=objc_getClass("NVMTLCommandBuffer");if(!base||class_getInstanceSize(base)!=656)return;
  Method a=class_getInstanceMethod(base,@selector(commit)),b=class_getInstanceMethod(base,@selector(enqueue));
  if(!a||!b||!method_getTypeEncoding(a)||!method_getTypeEncoding(b)||strcmp(method_getTypeEncoding(a),"v16@0:8")||strcmp(method_getTypeEncoding(b),"v16@0:8"))return;
  NSString*n=[@"KPAbandonedProducer_" stringByAppendingString:[NSUUID.UUID.UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@""]];Class sub=objc_allocateClassPair(base,n.UTF8String,0);if(!sub)return;
  if(!class_addMethod(sub,@selector(commit),(IMP)KPReusableRevoked,method_getTypeEncoding(a))||!class_addMethod(sub,@selector(enqueue),(IMP)KPReusableRevoked,method_getTypeEncoding(b))){objc_disposeClassPair(sub);return;}
  objc_registerClassPair(sub);if(class_getInstanceSize(sub)==class_getInstanceSize(base))result=sub;
 });return result;
}
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
- (BOOL)abandonExclusiveProducer:(id<MTLCommandBuffer>)buffer generation:(uint32_t)generation plan:(KPGPUCommandSelection*)plan error:(NSError**)error;
- (BOOL)retire:(NSError**)error;
@end
@implementation KPReusableIRContext
- (instancetype)init{if((self=[super init])){_pending=[NSMutableDictionary new];_ownerThread=NSThread.currentThread;_retired=YES;}return self;}
- (BOOL)idle:(NSError**)error{
 @synchronized(self){
  if(NSThread.currentThread!=_ownerThread)return fail(error,@"Reusable context owner thread differs");
  for(NSValue*key in [_pending.allKeys copy]){id<MTLCommandBuffer>b=_pending[key];if(b.status==MTLCommandBufferStatusError){_poisoned=YES;[_pending removeObjectForKey:key];KPReusableUnregister(b,self);}else if(b.status==MTLCommandBufferStatusCompleted){[_pending removeObjectForKey:key];KPReusableUnregister(b,self);}}
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
  NSValue*key=[NSValue valueWithPointer:(__bridge const void*)buffer];
  @synchronized(buffer){if(object_getClass(buffer)==KPReusableRevokedClass()&&KPReusableRevokedClass())return fail(error,@"Abandoned buffer cannot be tracked");if(_pending[key])return YES;[KPReusableOwners(buffer,YES)addObject:self];_pending[key]=buffer;}
  KPReusableIRContext*lease=self;
  [buffer addCompletedHandler:^(id<MTLCommandBuffer>done){@synchronized(lease){if(done.status==MTLCommandBufferStatusError)lease.poisoned=YES;if(lease.pending[key]==done){[lease.pending removeObjectForKey:key];KPReusableUnregister(done,lease);}}}];
  return YES;
 }
}
- (BOOL)abandonExclusiveProducer:(id<MTLCommandBuffer>)buffer generation:(uint32_t)generation plan:(KPGPUCommandSelection*)plan error:(NSError**)error{
 @synchronized(self){
  if(NSThread.currentThread!=_ownerThread||_retired||_poisoned||_preparing||!generation||_generation!=generation||_plan!=plan||!buffer||buffer.commandQueue!=_queue||!buffer.retainedReferences)return fail(error,@"Inactive or foreign reusable producer");
  NSValue*key=[NSValue valueWithPointer:(__bridge const void*)buffer];
  @synchronized(buffer){
   NSHashTable*owners=KPReusableOwners(buffer,NO);Class base=objc_getClass("NVMTLCommandBuffer"),revoked=KPReusableRevokedClass();
   if(_pending.count!=1||_pending[key]!=buffer||owners.count!=1||![owners containsObject:self]||!revoked||object_getClass(buffer)!=base||buffer.status!=MTLCommandBufferStatusNotEnqueued)return fail(error,@"Producer is not exclusive, native and uncommitted");
   object_setClass(buffer,revoked);if(object_getClass(buffer)!=revoked||buffer.status!=MTLCommandBufferStatusNotEnqueued)return fail(error,@"Producer revocation failed; lease retained");
   [_pending removeObjectForKey:key];@autoreleasepool{[owners removeObject:self];}return YES;
  }
 }
}
@end
