// SPDX-License-Identifier: MIT
// Public factories only. Invalid commands are never committed.
{
 Class nativeQueue=objc_getClass("NVMTLCommandQueue"),nativeBuffer=objc_getClass("NVMTLCommandBuffer"),nativeEncoder=objc_getClass("NVMTLComputeCommandEncoder_KEPLER_COMPUTE_A");
 id<MTLCommandQueue>other=[d newCommandQueue];
 MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=f;p.maxTotalThreadsPerThreadgroup=32;id<MTLComputePipelineState>limited=[d newComputePipelineStateWithDescriptor:p options:MTLPipelineOptionNone reflection:nil error:&error];if(!limited)return 14;
 id<MTLBuffer>rootBuffer=[d newBufferWithLength:8192 options:MTLResourceStorageModeShared];
 auto position=[](id<MTLComputeCommandEncoder>e)->uint64_t{Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");if(!v||ivar_getOffset(v)!=120)return 0;uintptr_t impl=0,push=0,value=0;memcpy(&impl,(const unsigned char*)(__bridge const void*)e+120,8);if(!impl)return 0;memcpy(&push,(const unsigned char*)impl+32,8);if(!push)return 0;memcpy(&value,(const void*)push,8);return value;};
 for(unsigned factory=0;factory<4;factory++)for(unsigned kind=0;kind<5;kind++){@autoreleasepool{
  id<MTLCommandBuffer>cb=nil;if(factory==0)cb=[q commandBuffer];else if(factory==1)cb=[q commandBufferWithUnretainedReferences];else{MTLCommandBufferDescriptor*desc=[MTLCommandBufferDescriptor new];desc.retainedReferences=factory==2;cb=[q commandBufferWithDescriptor:desc];}
  id<MTLComputeCommandEncoder>e=nil;if(kind==0)e=[cb computeCommandEncoder];else if(kind<3)e=[cb computeCommandEncoderWithDispatchType:kind==1?MTLDispatchTypeSerial:MTLDispatchTypeConcurrent];else{MTLComputePassDescriptor*desc=[MTLComputePassDescriptor computePassDescriptor];desc.dispatchType=kind==3?MTLDispatchTypeSerial:MTLDispatchTypeConcurrent;e=[cb computeCommandEncoderWithDescriptor:desc];}
  BOOL wrapped=class_getSuperclass(object_getClass(q))==nativeQueue&&class_getSuperclass(object_getClass(cb))==nativeBuffer&&class_getSuperclass(object_getClass(e))==nativeEncoder;
  [e setComputePipelineState:limited];[e setBuffer:rootBuffer offset:0 atIndex:0];uint64_t before=position(e);NSString*exception=nil;@try{[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(33,1,1)];}@catch(NSException*x){exception=x.name;}
  BOOL unchanged=position(e)==before;BOOL ok=wrapped&&before&&unchanged&&[exception isEqual:@"KeplerCPUICBUnsupported"]&&cb.retainedReferences==(factory==0||factory==2);[e endEncoding];
  [runs addObject:@{@"kind":@"automatic_public_factory",@"buffer_factory":@(factory),@"encoder_factory":@(kind),@"PASS":@(ok),@"retained_references":@(cb.retainedReferences),@"no_manual_adaptation":@YES,@"refused_before_native_cursor_write":@(unchanged),@"committed":@NO}];
 }}
 {
  id<MTLCommandBuffer>cb=[q commandBuffer];NSMutableSet*identities=[NSMutableSet new];BOOL ok=YES;
  for(unsigned i=0;i<8;i++){@autoreleasepool{id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[identities addObject:[NSValue valueWithPointer:(__bridge const void*)e]];[e setComputePipelineState:limited];[e setBuffer:rootBuffer offset:0 atIndex:0];NSString*exception=nil;@try{[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(33,1,1)];}@catch(NSException*x){exception=x.name;}ok=ok&&[exception isEqual:@"KeplerCPUICBUnsupported"];NSError*duplicate=nil;ok=ok&&[s adaptComputeEncoder:e error:&duplicate]&&!duplicate;[e endEncoding];NSError*ended=nil;ok=ok&&![s adaptComputeEncoder:e error:&ended]&&ended;}}
  [runs addObject:@{@"kind":@"automatic_repeated_encoders",@"PASS":@(ok),@"encoders":@8,@"distinct_addresses":@(identities.count),@"legacy_adaptation_idempotent":@YES,@"ended_readaptation_refused":@YES,@"committed":@NO}];
 }
 {
  id<MTLCommandBuffer>cb=[other commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];BOOL native=object_getClass(other)==nativeQueue&&object_getClass(cb)==nativeBuffer&&object_getClass(e)==nativeEncoder;NSError*foreign=nil;BOOL refused=![s adaptComputeEncoder:e error:&foreign]&&foreign;[e endEncoding];[runs addObject:@{@"kind":@"automatic_other_queue_isolation",@"PASS":@(native&&refused),@"ordinary_other_queue_unchanged":@(native),@"foreign_explicit_adaptation_refused":@(refused),@"committed":@NO}];
 }
 {
  NSLock*lock=[NSLock new];__block NSUInteger failures=0;dispatch_group_t group=dispatch_group_create();
  for(unsigned i=0;i<4;i++)dispatch_group_async(group,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{@autoreleasepool{
   BOOL ok=YES;@try{for(unsigned j=0;j<4;j++){@autoreleasepool{id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];ok=ok&&class_getSuperclass(object_getClass(cb))==nativeBuffer&&class_getSuperclass(object_getClass(e))==nativeEncoder;[e endEncoding];}}}@catch(NSException*x){ok=NO;}
   if(!ok){[lock lock];failures++;[lock unlock];}
  }});
  BOOL completed=!dispatch_group_wait(group,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC));[runs addObject:@{@"kind":@"automatic_concurrent_factories",@"PASS":@(completed&&!failures),@"workers":@4,@"buffers":@16,@"failures":@(failures),@"committed":@NO}];if(!completed)return 15;
 }
}
