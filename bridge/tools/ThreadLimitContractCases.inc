// SPDX-License-Identifier: MIT
// Included inside the active registered probe. All command buffers abandoned.
id<MTLComputePipelineState>unlimited=[d newComputePipelineStateWithFunction:f error:&error],limited32=nil;
for(NSNumber*n in @[@32,@64,@128,@256,@1024])for(unsigned async=0;async<2;async++){
 MTLComputePipelineDescriptor*request=[MTLComputePipelineDescriptor new];request.computeFunction=f;request.maxTotalThreadsPerThreadgroup=n.unsignedIntegerValue;request.label=[NSString stringWithFormat:@"limited-%@-%u",n,async];
 id<MTLComputePipelineState>pipeline=nil;MTLComputePipelineReflection*reflection=nil;NSError*failure=nil;NSUInteger callbacks=0;NSString*wanted=[request.label copy];
 if(!async)pipeline=[d newComputePipelineStateWithDescriptor:request options:MTLPipelineOption(3)reflection:&reflection error:&failure];
 else{KPContractReply*reply=[KPContractReply new];reply.lock=[NSLock new];dispatch_semaphore_t sem=dispatch_semaphore_create(0);
  [d newComputePipelineStateWithDescriptor:request options:MTLPipelineOption(3)completionHandler:^(id<MTLComputePipelineState>x,MTLComputePipelineReflection*y,NSError*z){[reply.lock lock];reply.count++;reply.pipeline=x;reply.reflection=y;reply.error=z;[reply.lock unlock];dispatch_semaphore_signal(sem);}];request.maxTotalThreadsPerThreadgroup=16;request.label=@"mutated";
  if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return 11;[reply.lock lock];pipeline=reply.pipeline;reflection=reply.reflection;failure=reply.error;callbacks=reply.count;[reply.lock unlock];
 }
 NSDictionary*proof=pipeline?objc_getAssociatedObject(pipeline,sel_registerName("KeplerMetalProducerEvidence-v1")):nil;NSDictionary*limit=proof[@"native_thread_limit"];uint64_t field=0;if(pipeline&&object_getClass(pipeline)==objc_getClass("NVMTLComputePipelineState"))memcpy(&field,(const unsigned char*)(__bridge const void*)pipeline+88,8);
 BOOL ok=pipeline&&pipeline!=unlimited&&!failure&&reflectionOK(reflection)&&pipeline.maxTotalThreadsPerThreadgroup==n.unsignedIntegerValue&&field==n.unsignedIntegerValue&&unlimited.maxTotalThreadsPerThreadgroup==1024&&[pipeline.label isEqual:wanted]&&[limit[@"native_getter_unchanged"]boolValue]&&[limit[@"native_before"]unsignedIntegerValue]==1024&&[limit[@"requested"]isEqual:n]&&(!async||callbacks==1);
 [runs addObject:@{@"kind":@"configured_thread_limit",@"requested":n,@"async":@(async),@"PASS":@(ok),@"native_field":@(field),@"baseline_limit":@(unlimited.maxTotalThreadsPerThreadgroup),@"proof":limit?:@{},@"callbacks":@(callbacks),@"error":failure.description?:@"",@"user_kernel_submitted":@NO}];if(!ok)continue;if(n.unsignedIntegerValue==32&&!async)limited32=pipeline;
}
if(!limited32)return 12;
auto position=[](id<MTLComputeCommandEncoder>e)->uint64_t{Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");if(!v||ivar_getOffset(v)!=120)return 0;uintptr_t impl=0,push=0,current=0;memcpy(&impl,(const unsigned char*)(__bridge const void*)e+120,8);if(!impl)return 0;memcpy(&push,(const unsigned char*)impl+32,8);if(!push)return 0;memcpy(&current,(const void*)push,8);return current;};
id<MTLBuffer>dummy=[d newBufferWithLength:8192 options:MTLResourceStorageModeShared],indirect=[d newBufferWithLength:64 options:MTLResourceStorageModeShared];uint32_t groups[3]={1,1,1};memcpy(indirect.contents,groups,sizeof groups);
for(unsigned api=0;api<3;api++)for(unsigned test=0;test<6;test++){
 id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];if(![s adaptComputeEncoder:e error:&error])return 13;[e setComputePipelineState:limited32];[e setBuffer:dummy offset:0 atIndex:0];
 MTLSize sizes[]={MTLSizeMake(32,1,1),MTLSizeMake(2,4,4),MTLSizeMake(33,1,1),MTLSizeMake(4,4,4),MTLSizeMake(0,1,1),MTLSizeMake(NSUIntegerMax,2,1)};MTLSize local=sizes[test];uint64_t before=position(e);NSString*exception=nil;
 @try{if(api==0)[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:local];else if(api==1)[e dispatchThreads:MTLSizeMake(32,1,1)threadsPerThreadgroup:local];else[e dispatchThreadgroupsWithIndirectBuffer:indirect indirectBufferOffset:0 threadsPerThreadgroup:local];}@catch(NSException*x){exception=x.name;}
 uint64_t after=position(e);BOOL refusal=test>=2;BOOL ok=before&&after&&(refusal?([exception isEqual:@"KeplerCPUICBUnsupported"]&&before==after):(!exception&&after>before));[e endEncoding];
 [runs addObject:@{@"kind":@"thread_limit_encoding",@"api":@(api),@"case":@(test),@"PASS":@(ok),@"expected_refusal":@(refusal),@"native_cursor_unchanged":@(before==after),@"exception":exception?:@"",@"command_buffer_committed":@NO}];
}
{
 id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];if(![s adaptComputeEncoder:e error:&error])return 13;[e setComputePipelineState:limited32];[e setComputePipelineState:unlimited];[e setBuffer:dummy offset:0 atIndex:0];uint64_t before=position(e);NSString*exception=nil;@try{[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(64,1,1)];}@catch(NSException*x){exception=x.name;}BOOL ok=!exception&&position(e)>before;[e endEncoding];[runs addObject:@{@"kind":@"thread_limit_pipeline_switch",@"PASS":@(ok),@"command_buffer_committed":@NO}];
}
