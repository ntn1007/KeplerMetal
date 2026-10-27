// SPDX-License-Identifier: MIT
// Adapt only the queue owned by this scope and its newly created buffers.
// No native/shared class method is replaced, and owners remain weak.
@interface KPAutoFactoryLink : NSObject
@property(nonatomic,weak) KPCPUICBScope *scope;
@property(nonatomic) Class originalClass;
@end
@implementation KPAutoFactoryLink
@end
@interface KPAutoBufferRecord : NSObject
@property(nonatomic,weak) id<MTLCommandBuffer> buffer;
@property(nonatomic) Class originalClass,dynamicClass;
@end
@implementation KPAutoBufferRecord
@end
namespace {
char automaticFactoryKey;
std::map<uintptr_t,Class>automaticQueueClasses,automaticBufferClasses,automaticRenderGuardClasses;
thread_local NSUInteger queueFactoryDepth=0,computeFactoryDepth=0;

void automaticEvent(__unsafe_unretained KPCPUICBScope*s,NSDictionary*row){
 NSMutableArray*events=s.eventRows;@synchronized(events){[events addObject:row];}
}
id<MTLComputeCommandEncoder>automaticComputeEncoder(id self,SEL selector);
id<MTLComputeCommandEncoder>automaticComputeDispatch(id self,SEL selector,MTLDispatchType type);
id<MTLComputeCommandEncoder>automaticComputeDescriptor(id self,SEL selector,MTLComputePassDescriptor*descriptor);
id<MTLRenderCommandEncoder>automaticRenderEncoder(id self,SEL selector,MTLRenderPassDescriptor*descriptor);

id<MTLCommandBuffer>adaptAutomaticBuffer(KPCPUICBScope*s,id<MTLCommandBuffer>buffer,SEL factory){
 if(!buffer||s.restored)return buffer;
 KPAutoFactoryLink*old=objc_getAssociatedObject(buffer,&automaticFactoryKey);
 if(old){if(old.scope==s)return buffer;reject(@"Command buffer already belongs to another automatic scope");}
 Class original=object_getClass(buffer),dynamic=nil;
 if(original!=objc_getClass("NVMTLCommandBuffer")||class_getInstanceSize(original)!=656||buffer.commandQueue!=s.queue||buffer.status!=MTLCommandBufferStatusNotEnqueued)reject(@"Native automatic command-buffer profile differs");
 {
  std::lock_guard<std::mutex>lock(installMutex);
  dynamic=scopedClass(automaticBufferClasses,original,@"KPAutomaticCommandBuffer_",@selector(computeCommandEncoder),(IMP)automaticComputeEncoder,nullptr);
  if(dynamic&&(!installRenderOverride(dynamic,original,@selector(computeCommandEncoderWithDispatchType:),(IMP)automaticComputeDispatch)||!installRenderOverride(dynamic,original,@selector(computeCommandEncoderWithDescriptor:),(IMP)automaticComputeDescriptor)||!installRenderOverride(dynamic,original,@selector(renderCommandEncoderWithDescriptor:),(IMP)automaticRenderEncoder)))dynamic=nil;
 }
 if(!dynamic)reject(@"Cannot install buffer-local compute factories");
 NSMutableIndexSet*expired=[NSMutableIndexSet new];for(NSUInteger i=0;i<s.automaticBuffers.count;i++)if(!((KPAutoBufferRecord*)s.automaticBuffers[i]).buffer)[expired addIndex:i];[s.automaticBuffers removeObjectsAtIndexes:expired];
 KPAutoFactoryLink*link=[KPAutoFactoryLink new];link.scope=s;link.originalClass=original;objc_setAssociatedObject(buffer,&automaticFactoryKey,link,OBJC_ASSOCIATION_RETAIN_NONATOMIC);object_setClass(buffer,dynamic);
 KPAutoBufferRecord*record=[KPAutoBufferRecord new];record.buffer=buffer;record.originalClass=original;record.dynamicClass=dynamic;[s.automaticBuffers addObject:record];
 automaticEvent(s,@{@"operation":@"automatic_command_buffer",@"selector":NSStringFromSelector(factory),@"retained_references":@(buffer.retainedReferences),@"class_layout_preserved":@(class_getInstanceSize(dynamic)==class_getInstanceSize(original))});return buffer;
}

id<MTLComputeCommandEncoder>adaptAutomaticEncoder(KPCPUICBScope*s,id<MTLComputeCommandEncoder>encoder,SEL factory){
 if(!encoder||s.restored)return encoder;
 // Some native factories may recycle an ended encoder. Only a new native
 // factory call may begin that new recording; explicit re-adaptation cannot.
 KPScopeLink*previous=objc_getAssociatedObject(encoder,&contextKey);
 if(previous&&previous.scope==s&&previous.computeEncodingEnded){
  if(class_getSuperclass(object_getClass(encoder))==previous.originalComputeClass){previous.computeEncodingEnded=NO;previous.callerComputePipeline=nil;}
  else if(object_getClass(encoder)==previous.originalComputeClass){
   objc_setAssociatedObject(encoder,&contextKey,nil,OBJC_ASSOCIATION_ASSIGN);NSMutableIndexSet*same=[NSMutableIndexSet new];for(NSUInteger i=0;i<s.adapted.count;i++)if(((KPAdaptedEncoder*)s.adapted[i]).encoder==encoder)[same addIndex:i];[s.adapted removeObjectsAtIndexes:same];
  }else reject(@"Recycled native encoder class differs");
 }
 NSError*error=nil;if(![s adaptComputeEncoder:encoder error:&error])reject(error.localizedDescription?:@"Automatic compute adaptation failed");
 automaticEvent(s,@{@"operation":@"automatic_compute_encoder",@"selector":NSStringFromSelector(factory),@"explicit_adaptation_required":@NO});return encoder;
}

// Native allocation may block on a queue pool; never hold the scope lock
// across that call. Restore is serialized only with publication/adaptation.
id<MTLCommandBuffer>automaticQueueBuffer(id self,SEL selector){
 KPAutoFactoryLink*link=objc_getAssociatedObject(self,&automaticFactoryKey);KPCPUICBScope*s=link.scope;Class original=link.originalClass?:objc_getClass("NVMTLCommandQueue");
 queueFactoryDepth++;id<MTLCommandBuffer>buffer=nil;@try{typedef id<MTLCommandBuffer>(*F)(id,SEL);buffer=((F)class_getMethodImplementation(original,selector))(self,selector);if(queueFactoryDepth==1&&s){@synchronized(s.factoryLock){if(!s.restored)buffer=adaptAutomaticBuffer(s,buffer,selector);}}}@finally{queueFactoryDepth--;}return buffer;
}
id<MTLCommandBuffer>automaticQueueDescriptor(id self,SEL selector,MTLCommandBufferDescriptor*descriptor){
 KPAutoFactoryLink*link=objc_getAssociatedObject(self,&automaticFactoryKey);KPCPUICBScope*s=link.scope;Class original=link.originalClass?:objc_getClass("NVMTLCommandQueue");
 queueFactoryDepth++;id<MTLCommandBuffer>buffer=nil;@try{typedef id<MTLCommandBuffer>(*F)(id,SEL,MTLCommandBufferDescriptor*);buffer=((F)class_getMethodImplementation(original,selector))(self,selector,descriptor);if(queueFactoryDepth==1&&s){@synchronized(s.factoryLock){if(!s.restored)buffer=adaptAutomaticBuffer(s,buffer,selector);}}}@finally{queueFactoryDepth--;}return buffer;
}
id<MTLComputeCommandEncoder>automaticComputeEncoder(id self,SEL selector){
 KPAutoFactoryLink*link=objc_getAssociatedObject(self,&automaticFactoryKey);KPCPUICBScope*s=link.scope;Class original=link.originalClass?:objc_getClass("NVMTLCommandBuffer");
 computeFactoryDepth++;id<MTLComputeCommandEncoder>encoder=nil;@try{typedef id<MTLComputeCommandEncoder>(*F)(id,SEL);encoder=((F)class_getMethodImplementation(original,selector))(self,selector);if(computeFactoryDepth==1&&s){@synchronized(s.factoryLock){if(!s.restored&&s.automaticComputeEnabled)encoder=adaptAutomaticEncoder(s,encoder,selector);}}}@finally{computeFactoryDepth--;}return encoder;
}
id<MTLComputeCommandEncoder>automaticComputeDispatch(id self,SEL selector,MTLDispatchType type){
 KPAutoFactoryLink*link=objc_getAssociatedObject(self,&automaticFactoryKey);KPCPUICBScope*s=link.scope;Class original=link.originalClass?:objc_getClass("NVMTLCommandBuffer");
 computeFactoryDepth++;id<MTLComputeCommandEncoder>encoder=nil;@try{typedef id<MTLComputeCommandEncoder>(*F)(id,SEL,MTLDispatchType);encoder=((F)class_getMethodImplementation(original,selector))(self,selector,type);if(computeFactoryDepth==1&&s){@synchronized(s.factoryLock){if(!s.restored&&s.automaticComputeEnabled)encoder=adaptAutomaticEncoder(s,encoder,selector);}}}@finally{computeFactoryDepth--;}return encoder;
}
id<MTLComputeCommandEncoder>automaticComputeDescriptor(id self,SEL selector,MTLComputePassDescriptor*descriptor){
 KPAutoFactoryLink*link=objc_getAssociatedObject(self,&automaticFactoryKey);KPCPUICBScope*s=link.scope;Class original=link.originalClass?:objc_getClass("NVMTLCommandBuffer");
 computeFactoryDepth++;id<MTLComputeCommandEncoder>encoder=nil;@try{typedef id<MTLComputeCommandEncoder>(*F)(id,SEL,MTLComputePassDescriptor*);encoder=((F)class_getMethodImplementation(original,selector))(self,selector,descriptor);if(computeFactoryDepth==1&&s){@synchronized(s.factoryLock){if(!s.restored&&s.automaticComputeEnabled)encoder=adaptAutomaticEncoder(s,encoder,selector);}}}@finally{computeFactoryDepth--;}return encoder;
}

void guardedRenderRange(id self,SEL selector,id buffer,NSRange range){
 if([buffer isKindOfClass:KPComputeICB.class])reject(@"Project render ICB cannot execute on an unqualified native render pass");
 Class original=class_getSuperclass(object_getClass(self));typedef void(*F)(id,SEL,id,NSRange);((F)class_getMethodImplementation(original,selector))(self,selector,buffer,range);
}
void guardedRenderIndirect(id self,SEL selector,id buffer,id indirect,NSUInteger offset){
 if([buffer isKindOfClass:KPComputeICB.class])reject(@"Project render ICB cannot execute on an unqualified native render pass");
 Class original=class_getSuperclass(object_getClass(self));typedef void(*F)(id,SEL,id,id,NSUInteger);((F)class_getMethodImplementation(original,selector))(self,selector,buffer,indirect,offset);
}
id<MTLRenderCommandEncoder>guardNativeRenderEncoder(KPCPUICBScope*s,id<MTLRenderCommandEncoder>encoder,id<MTLCommandBuffer>cb){
 Class original=object_getClass(encoder),native=objc_getClass("NVMTLRenderCommandEncoder_KEPLER_A"),dynamic=nil;Ivar slot=class_getInstanceVariable(original,"_commandBuffer");
 if(original!=native||class_getInstanceSize(original)!=128||!slot||ivar_getOffset(slot)!=32||object_getIvar(encoder,slot)!=cb)return nil;
 {std::lock_guard<std::mutex>lock(installMutex);dynamic=scopedClass(automaticRenderGuardClasses,original,@"KPGuardedRenderEncoder_",@selector(executeCommandsInBuffer:withRange:),(IMP)guardedRenderRange,nullptr);if(dynamic&&!installRenderOverride(dynamic,original,@selector(executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:),(IMP)guardedRenderIndirect))dynamic=nil;}
 if(!dynamic)return nil;
 NSMutableIndexSet*expired=[NSMutableIndexSet new];for(NSUInteger i=0;i<s.adapted.count;i++)if(!((KPAdaptedEncoder*)s.adapted[i]).encoder)[expired addIndex:i];s.releasedEncoderCount+=expired.count;[s.adapted removeObjectsAtIndexes:expired];
 linkScope(encoder,s);object_setClass(encoder,dynamic);KPAdaptedEncoder*record=[KPAdaptedEncoder new];record.encoder=encoder;record.originalClass=original;[s.adapted addObject:record];return encoder;
}

id<MTLRenderCommandEncoder>automaticRenderEncoder(id self,SEL selector,MTLRenderPassDescriptor*descriptor){
 KPAutoFactoryLink*link=objc_getAssociatedObject(self,&automaticFactoryKey);KPCPUICBScope*s=link.scope;Class original=link.originalClass?:objc_getClass("NVMTLCommandBuffer");
 BOOL observe=NO;if(s)@synchronized(s.factoryLock){observe=!s.restored&&s.automaticRenderEnabled;}
 MTLRenderPassDescriptor*pass=observe?[descriptor copy]:nil;typedef id<MTLRenderCommandEncoder>(*F)(id,SEL,MTLRenderPassDescriptor*);id<MTLRenderCommandEncoder>encoder=((F)class_getMethodImplementation(original,selector))(self,selector,descriptor);
 if(!encoder||!s||!observe)return encoder;
 @synchronized(s.factoryLock){
  if(s.restored||!s.automaticRenderEnabled)return encoder;
  KPScopeLink*previous=objc_getAssociatedObject(encoder,&contextKey);
  if(previous){
   Class current=object_getClass(encoder),native=objc_getClass("NVMTLRenderCommandEncoder_KEPLER_A");
   if(previous.scope!=s||class_getSuperclass(current)!=native){[encoder endEncoding];reject(@"Recycled render encoder has foreign ownership; discard command buffer");}
   object_setClass(encoder,native);objc_setAssociatedObject(encoder,&contextKey,nil,OBJC_ASSOCIATION_ASSIGN);
   NSMutableIndexSet*same=[NSMutableIndexSet new];for(NSUInteger i=0;i<s.adapted.count;i++)if(((KPAdaptedEncoder*)s.adapted[i]).encoder==encoder)[same addIndex:i];[s.adapted removeObjectsAtIndexes:same];
  }
  NSError*error=nil;
  BOOL eligible=[s validateRenderPassProfile:pass commandBuffer:self error:&error];id<MTLRenderCommandEncoder>adapted=eligible?[s adoptNativeRenderEncoder:encoder descriptor:pass commandBuffer:self error:&error]:nil;
  if(!adapted){id<MTLRenderCommandEncoder>guarded=guardNativeRenderEncoder(s,encoder,self);if(!guarded){[encoder endEncoding];reject(@"Cannot guard an unqualified render encoder; discard command buffer");}automaticEvent(s,@{@"operation":@"automatic_render_passthrough",@"selector":NSStringFromSelector(selector),@"reason":eligible?@"encoder_profile":@"unsupported_pass",@"project_ICB_guarded":@YES});return guarded;}
  automaticEvent(s,@{@"operation":@"automatic_render_encoder",@"selector":NSStringFromSelector(selector),@"explicit_adaptation_required":@NO});return adapted;
 }
}

BOOL ensureAutomaticFactories(KPCPUICBScope*s,NSError**error){
 if(s.restored)return fail(error,@"Active scope required for automatic factories");
 if(s.originalQueueClass){KPAutoFactoryLink*link=objc_getAssociatedObject(s.queue,&automaticFactoryKey);return link.scope==s?YES:fail(error,@"Automatic queue context changed");}
 Class original=object_getClass(s.queue),dynamic=nil;
 if(original!=objc_getClass("NVMTLCommandQueue")||class_getInstanceSize(original)!=688||objc_getAssociatedObject(s.queue,&automaticFactoryKey))return fail(error,@"Native automatic queue profile differs");
 {
  std::lock_guard<std::mutex>lock(installMutex);
  dynamic=scopedClass(automaticQueueClasses,original,@"KPAutomaticQueue_",@selector(commandBuffer),(IMP)automaticQueueBuffer,error);
  if(dynamic&&(!installRenderOverride(dynamic,original,@selector(commandBufferWithUnretainedReferences),(IMP)automaticQueueBuffer)||!installRenderOverride(dynamic,original,@selector(commandBufferWithDescriptor:),(IMP)automaticQueueDescriptor)))dynamic=nil;
 }
 if(!dynamic)return fail(error,@"Cannot install queue-local command-buffer factories");
 s.originalQueueClass=original;s.automaticBuffers=[NSMutableArray new];KPAutoFactoryLink*link=[KPAutoFactoryLink new];link.scope=s;link.originalClass=original;objc_setAssociatedObject(s.queue,&automaticFactoryKey,link,OBJC_ASSOCIATION_RETAIN_NONATOMIC);object_setClass(s.queue,dynamic);return YES;
}
BOOL enableAutomaticComputeFactories(KPCPUICBScope*s,NSError**error){
 @synchronized(s.factoryLock){
  if(s.restored||!s.pipeline)return fail(error,@"Active compute scope required for automatic factories");
  if(!ensureAutomaticFactories(s,error))return NO;if(s.automaticComputeEnabled)return YES;s.automaticComputeEnabled=YES;
  automaticEvent(s,@{@"operation":@"automatic_compute_factories_enabled",@"queue_instance_only":@YES,@"shared_native_methods_replaced":@NO});return YES;
 }
}
BOOL enableAutomaticRenderFactories(KPCPUICBScope*s,NSError**error){
 @synchronized(s.factoryLock){
  if(s.restored||!s.renderEngine)return fail(error,@"Active render scope required for automatic factories");
  if(!ensureAutomaticFactories(s,error))return NO;if(s.automaticRenderEnabled)return YES;s.automaticRenderEnabled=YES;
  automaticEvent(s,@{@"operation":@"automatic_render_factories_enabled",@"queue_instance_only":@YES,@"shared_native_methods_replaced":@NO});return YES;
 }
}

void restoreAutomaticComputeFactories(__unsafe_unretained KPCPUICBScope*s){
 BOOL renderEnabled=s.automaticRenderEnabled;s.automaticComputeEnabled=NO;s.automaticRenderEnabled=NO;
 NSUInteger live=0,expired=0;for(KPAutoBufferRecord*record in s.automaticBuffers){id buffer=record.buffer;if(!buffer){expired++;continue;}if(object_getClass(buffer)==record.dynamicClass){object_setClass(buffer,record.originalClass);live++;}objc_setAssociatedObject(buffer,&automaticFactoryKey,nil,OBJC_ASSOCIATION_ASSIGN);}[s.automaticBuffers removeAllObjects];
 if(s.originalQueueClass){object_setClass(s.queue,s.originalQueueClass);objc_setAssociatedObject(s.queue,&automaticFactoryKey,nil,OBJC_ASSOCIATION_ASSIGN);automaticEvent(s,@{@"operation":@"automatic_compute_factories_restored",@"live_buffers":@(live),@"expired_buffers":@(expired),@"queue_class_restored":@(object_getClass(s.queue)==s.originalQueueClass)});if(renderEnabled)automaticEvent(s,@{@"operation":@"automatic_render_factories_restored",@"queue_class_restored":@(object_getClass(s.queue)==s.originalQueueClass)});}
}
}
