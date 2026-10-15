// Included inside the active registered CPU-probe scope; no user dispatch.
for(NSString*test in @[@"max16",@"max32",@"max2048",@"active_stage",@"indirect",@"adding_binary",@"call_stack",@"nonroot_mutability",@"options4",@"options8"]){
 for(unsigned asynchronous=0;asynchronous<2;asynchronous++){
  MTLComputePipelineDescriptor*bad=[MTLComputePipelineDescriptor new];bad.computeFunction=f;MTLPipelineOption opts=MTLPipelineOption(3);
  if([test isEqual:@"max16"])bad.maxTotalThreadsPerThreadgroup=16;
  if([test isEqual:@"max32"])bad.maxTotalThreadsPerThreadgroup=32;
  if([test isEqual:@"max2048"])bad.maxTotalThreadsPerThreadgroup=2048;
  if([test isEqual:@"active_stage"])bad.stageInputDescriptor.attributes[0].format=MTLAttributeFormatFloat4;
  if([test isEqual:@"indirect"])bad.supportIndirectCommandBuffers=YES;
  if([test isEqual:@"adding_binary"])bad.supportAddingBinaryFunctions=YES;
  if([test isEqual:@"call_stack"])bad.maxCallStackDepth=2;
  if([test isEqual:@"nonroot_mutability"])bad.buffers[1].mutability=MTLMutabilityMutable;
  if([test isEqual:@"options4"])opts=MTLPipelineOption(4);
  if([test isEqual:@"options8"])opts=MTLPipelineOption(8);
  NSError*rejection=nil;MTLComputePipelineReflection*ref=nil;id<MTLComputePipelineState>invalid=nil;NSUInteger callbacks=0;
  if(!asynchronous)invalid=[d newComputePipelineStateWithDescriptor:bad options:opts reflection:&ref error:&rejection];
  else{
   KPContractReply*reply=[KPContractReply new];reply.lock=[NSLock new];dispatch_semaphore_t sem=dispatch_semaphore_create(0);
   [d newComputePipelineStateWithDescriptor:bad options:opts completionHandler:^(id<MTLComputePipelineState>x,MTLComputePipelineReflection*y,NSError*z){[reply.lock lock];reply.count++;reply.pipeline=x;reply.reflection=y;reply.error=z;[reply.lock unlock];dispatch_semaphore_signal(sem);}];
   if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return 8;
   [reply.lock lock];invalid=reply.pipeline;ref=reply.reflection;rejection=reply.error;callbacks=reply.count;[reply.lock unlock];
  }
  BOOL refused=!invalid&&!ref&&rejection&&(!asynchronous||callbacks==1);
  [runs addObject:@{@"kind":@"descriptor_rejection",@"case":test,@"async":@(asynchronous),@"PASS":@(refused),@"callbacks":@(callbacks),@"error":rejection.description?:@"",@"user_kernel_submitted":@NO}];
 }
}
for(unsigned asynchronous=0;asynchronous<2;asynchronous++)for(unsigned flags: {4u,8u}){
 NSError*rejection=nil;MTLComputePipelineReflection*ref=nil;id<MTLComputePipelineState>invalid=nil;NSUInteger callbacks=0;
 if(!asynchronous)invalid=[d newComputePipelineStateWithFunction:f options:MTLPipelineOption(flags)reflection:&ref error:&rejection];
 else{
  KPContractReply*reply=[KPContractReply new];reply.lock=[NSLock new];dispatch_semaphore_t sem=dispatch_semaphore_create(0);
  [d newComputePipelineStateWithFunction:f options:MTLPipelineOption(flags)completionHandler:^(id<MTLComputePipelineState>x,MTLComputePipelineReflection*y,NSError*z){[reply.lock lock];reply.count++;reply.pipeline=x;reply.reflection=y;reply.error=z;[reply.lock unlock];dispatch_semaphore_signal(sem);}];
  if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return 8;
  [reply.lock lock];invalid=reply.pipeline;ref=reply.reflection;rejection=reply.error;callbacks=reply.count;[reply.lock unlock];
 }
 [runs addObject:@{@"kind":@"function_options_rejection",@"options":@(flags),@"async":@(asynchronous),@"PASS":@(!invalid&&!ref&&rejection&&(!asynchronous||callbacks==1)),@"callbacks":@(callbacks),@"error":rejection.description?:@"",@"user_kernel_submitted":@NO}];
}
