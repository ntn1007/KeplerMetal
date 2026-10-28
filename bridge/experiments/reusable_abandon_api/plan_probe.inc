// SPDX-License-Identifier: MIT
// Included only in an isolated modified copy of the dataflow client.
if(trial==0){
 witnessStale=[q commandBuffer];if(!witnessStale||![plan reserveCommandIRProducerInCommandBuffer:witnessStale error:&error])return 81;
 id<MTLComputeCommandEncoder>e=[witnessStale computeCommandEncoder];if(!e)return 82;
 [e setComputePipelineState:writer];[e setBuffer:root offset:0 atIndex:0];
 for(id<MTLBuffer>r in plan.commandIRProducerResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];
 [e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];
 BOOL busyRefused=NO;@try{[target resetWithRange:NSMakeRange(0,rows)];}@catch(NSException*x){busyRefused=[x.reason containsString:@"uncompleted"];}
 if(!busyRefused)return 83;
 id lease=[plan valueForKey:@"reusableContext"];NSMutableDictionary*pending=[lease valueForKey:@"pending"];NSValue*key=[NSValue valueWithPointer:(__bridge const void*)witnessStale];
 if(!lease||pending.count!=1||pending[key]!=witnessStale)return 84;
 if(witnessShared){
  id shadow=[NSClassFromString(@"KPReusableIRContext") new];[shadow setValue:q forKey:@"queue"];[shadow setValue:@19 forKey:@"generation"];[shadow setValue:@NO forKey:@"retired"];
  typedef BOOL(*Track)(id,SEL,id,uint32_t,NSError**);NSError*e=nil;
  if(!shadow||!((Track)objc_msgSend)(shadow,NSSelectorFromString(@"track:generation:error:"),witnessStale,19,&e))return 89;
  e=nil;BOOL refused=![plan experimentallyAbandonReusableProducer:witnessStale error:&e]&&e!=nil;
  BOOL retained=pending.count==1&&pending[key]==witnessStale&&[[shadow valueForKey:@"pending"]count]==1&&witnessStale.status==MTLCommandBufferStatusNotEnqueued&&object_getClass(witnessStale)==objc_getClass("NVMTLCommandBuffer");
  emit(@{@"scenario":@"shared_owner",@"refused":@(refused),@"both_owners_retained":@(retained),@"error":e.localizedDescription?:@"",@"producer_submitted":@NO,@"system_modified":@NO});return refused&&retained?0:89;
 }
 id<MTLCommandBuffer>wrong=[q commandBuffer];NSError*negative=nil;
 if([plan experimentallyAbandonReusableProducer:wrong error:&negative]||!negative||pending.count!=1||pending[key]!=witnessStale)return 84;
 __block BOOL wrongThreadRefused=NO;dispatch_semaphore_t wait=dispatch_semaphore_create(0);
 dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{@autoreleasepool{NSError*e=nil;wrongThreadRefused=![plan experimentallyAbandonReusableProducer:witnessStale error:&e]&&e!=nil;dispatch_semaphore_signal(wait);}});
 if(dispatch_semaphore_wait(wait,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC))||!wrongThreadRefused||pending.count!=1)return 84;
 if(![plan experimentallyAbandonReusableProducer:witnessStale error:&error])return 84;
 if(!witnessBlock(witnessStale,@selector(commit))||!witnessBlock(witnessStale,@selector(enqueue))||witnessStale.status!=MTLCommandBufferStatusNotEnqueued)return 85;
 negative=nil;if(pending.count||[plan valueForKey:@"producerBuffer"]||[plan experimentallyAbandonReusableProducer:witnessStale error:&negative]||!negative)return 86;
 negative=nil;if([plan reserveCommandIRProducerInCommandBuffer:witnessStale error:&negative]||!negative||pending.count)return 86;
 witnessGeneration=[[plan valueForKey:@"reusableGeneration"]unsignedIntValue];witnessPrepared=YES;
}
