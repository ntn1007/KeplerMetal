// SPDX-License-Identifier: MIT
// Public library/function calls after one explicit library registration.
{
 NSMutableArray*held=[NSMutableArray new];
 for(unsigned form=0;form<3;form++){
  NSError*failure=nil;id<MTLLibrary>library=nil;NSString*path=[assets stringByAppendingPathComponent:@"producer.metallib"];
  if(form==0){dispatch_data_t bytes=dispatch_data_create(producer.bytes,producer.length,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{(void)producer.length;});library=[d newLibraryWithData:bytes error:&failure];}
  else if(form==1)library=[d newLibraryWithURL:[NSURL fileURLWithPath:path]error:&failure];else library=[d newLibraryWithFile:path error:&failure];
  if(!library||failure)return 20;
  for(unsigned kind=0;kind<10;kind++){
   id<MTLFunction>function=nil;NSError*err=nil;NSUInteger callbacks=0;NSString*exception=nil;MTLFunctionConstantValues*values=[MTLFunctionConstantValues new];if(kind==3){uint32_t value=123;[values setConstantValue:&value type:MTLDataTypeUInt atIndex:0];}
   MTLFunctionDescriptor*request=[MTLFunctionDescriptor functionDescriptor];request.name=@"encode_dataflow_basic";if(kind==5)request.constantValues=values;if(kind==6)request.specializedName=@"library_alias";if(kind==7)request.options=MTLFunctionOptionCompileToBinary;
   @try{
    if(kind==0)function=[library newFunctionWithName:@"encode_dataflow_basic"];
    else if(kind<4)function=[library newFunctionWithName:@"encode_dataflow_basic" constantValues:kind==1?nil:values error:&err];
    else if(kind<8)function=[library newFunctionWithDescriptor:request error:&err];
    else{
     KPContractReply*unused=nil;(void)unused;NSLock*lock=[NSLock new];__block id<MTLFunction>reply=nil;__block NSError*errorReply=nil;__block NSUInteger count=0;dispatch_semaphore_t sem=dispatch_semaphore_create(0);
     void(^complete)(id<MTLFunction>,NSError*)=^(id<MTLFunction>x,NSError*y){[lock lock];reply=x;errorReply=y;count++;[lock unlock];dispatch_semaphore_signal(sem);};
     if(kind==8)[library newFunctionWithName:@"encode_dataflow_basic" constantValues:values completionHandler:complete];else[library newFunctionWithDescriptor:request completionHandler:complete];request.name=@"absent-after-call";
     if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return 21;[lock lock];function=reply;err=errorReply;callbacks=count;[lock unlock];
    }
   }@catch(NSException*x){exception=x.reason?:x.name;}
   BOOL negative=kind==7,ok=NO;id<MTLComputePipelineState>pipeline=nil;id<MTLArgumentEncoder>encoder=nil;
   if(negative)ok=!function&&err&&!exception;
   else if(function&&!err&&!exception){NSError*errorPipeline=nil;pipeline=[d newComputePipelineStateWithFunction:function error:&errorPipeline];encoder=[function newArgumentEncoderWithBufferIndex:0];ok=pipeline&&!errorPipeline&&[NSStringFromClass(object_getClass(function))hasPrefix:@"KPIRFunction_"]&&[NSStringFromClass(object_getClass(encoder))hasPrefix:@"KPCommandIRArgumentEncoder"]&&encoder.encodedLength==48&&[function.name isEqual:kind==6?@"library_alias":@"encode_dataflow_basic"]&&(!callbacks||callbacks==1);[held addObject:function];}
   [runs addObject:@{@"kind":@"automatic_library_function",@"library_form":@(form),@"function_factory":@(kind),@"PASS":@(ok),@"expected_refusal":@(negative),@"callbacks":@(callbacks),@"name":function.name?:@"",@"native_library_subclass":@([NSStringFromClass(object_getClass(library))hasPrefix:@"KPIRLibrary_"]),@"native_pipeline":@(pipeline!=nil),@"error":err.description?:@"",@"exception":exception?:@"",@"user_kernel_submitted":@NO}];
  }
  BOOL unknown=[library newFunctionWithName:@"not_a_registered_function"]==nil;[runs addObject:@{@"kind":@"library_unknown_function",@"library_form":@(form),@"PASS":@(unknown),@"user_kernel_submitted":@NO}];
 }
 {
  NSError*failure=nil;id<MTLLibrary>other=[d newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"consumer.metallib"]]error:&failure];id<MTLFunction>native=[other newFunctionWithName:@"dependency_seed"];id<MTLComputePipelineState>pipeline=[d newComputePipelineStateWithFunction:native error:&failure];BOOL unchanged=object_getClass(other)==objc_getClass("_MTLLibrary")&&object_getClass(native)==objc_getClass("_MTLFunctionInternal")&&pipeline;[runs addObject:@{@"kind":@"unregistered_library_passthrough",@"PASS":@(unchanged),@"user_kernel_submitted":@NO}];
 }
}
