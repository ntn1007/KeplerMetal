// SPDX-License-Identifier: MIT
// One empty buffer releases a deliberately full one-buffer native queue pool.
{
 id<MTLCommandBuffer>first=nil;@autoreleasepool{first=[q commandBuffer];}
 dispatch_semaphore_t entered=dispatch_semaphore_create(0),finished=dispatch_semaphore_create(0);__block pthread_t worker=nullptr;__block BOOL nativeResult=NO;__block NSString*failure=nil;
 dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{@autoreleasepool{
  worker=pthread_self();dispatch_semaphore_signal(entered);@try{id<MTLCommandBuffer>later=[q commandBuffer];nativeResult=later&&object_getClass(later)==objc_getClass("NVMTLCommandBuffer");}@catch(NSException*x){failure=x.reason?:x.name;}
 }dispatch_semaphore_signal(finished);});
 if(dispatch_semaphore_wait(entered,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC)))return 16;
 BOOL observedWaiting=NO,earlyDone=NO;
 for(unsigned retry=0;retry<200;retry++){
  if(!dispatch_semaphore_wait(finished,DISPATCH_TIME_NOW)){earlyDone=YES;break;}
  thread_basic_info_data_t info={};mach_msg_type_number_t count=THREAD_BASIC_INFO_COUNT;
  if(thread_info(pthread_mach_thread_np(worker),THREAD_BASIC_INFO,(thread_info_t)&info,&count)==KERN_SUCCESS&&info.run_state==TH_STATE_WAITING){observedWaiting=YES;break;}
  usleep(1000);
 }
 NSTimeInterval before=NSProcessInfo.processInfo.systemUptime;[s restore];NSTimeInterval elapsed=NSProcessInfo.processInfo.systemUptime-before;
 BOOL restored=object_getClass(q)==objc_getClass("NVMTLCommandQueue")&&object_getClass(first)==objc_getClass("NVMTLCommandBuffer");
 [first commit];[first waitUntilCompleted];NSUInteger emptyStatus=first.status;first=nil;
 BOOL complete=earlyDone||!dispatch_semaphore_wait(finished,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC));
 [runs addObject:@{@"kind":@"automatic_restore_during_native_pool_wait",@"PASS":@(observedWaiting&&!earlyDone&&restored&&complete&&nativeResult&&!failure&&elapsed<1.0&&emptyStatus==MTLCommandBufferStatusCompleted),@"worker_waiting_observed":@(observedWaiting),@"early_completion":@(earlyDone),@"restore_seconds":@(elapsed),@"classes_restored":@(restored),@"worker_completed":@(complete),@"returned_buffer_native":@(nativeResult),@"exception":failure?:@"",@"empty_command_buffers_submitted":@1,@"empty_command_buffer_status":@(emptyStatus),@"user_kernel_dispatches":@0}];if(!complete)return 16;
}
