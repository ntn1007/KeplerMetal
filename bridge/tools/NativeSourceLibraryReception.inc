// SPDX-License-Identifier: MIT
// Ordinary public Metal factory reception for source-lowered native producers.
static NSDictionary*nativeLibraryReception=nil;
static id<MTLLibrary>nativeLibraryOwner=nil;
static id<MTLFunction>nativeSourceFunctionFromLibrary(id<MTLLibrary>library,NSString*name,NSUInteger f,NSError**error,NSUInteger*callbackCount){
 id<MTLFunction>function=nil;MTLFunctionConstantValues*values=[MTLFunctionConstantValues new];if(f==3){uint32_t unused=123;[values setConstantValue:&unused type:MTLDataTypeUInt atIndex:0];}
 MTLFunctionDescriptor*descriptor=[MTLFunctionDescriptor functionDescriptor];descriptor.name=name;if(f==5)descriptor.constantValues=values;if(f==6)descriptor.specializedName=[@"alias_" stringByAppendingString:name];NSUInteger callbacks=0;
 if(f==0)function=[library newFunctionWithName:name];
 else if(f<4)function=[library newFunctionWithName:name constantValues:f==1?nil:values error:error];
 else if(f<7)function=[library newFunctionWithDescriptor:descriptor error:error];
 else{
  NSLock*lock=[NSLock new];__block id<MTLFunction>reply=nil;__block NSError*failure=nil;__block NSUInteger count=0;dispatch_semaphore_t sem=dispatch_semaphore_create(0);
  void(^complete)(id<MTLFunction>,NSError*)=^(id<MTLFunction>x,NSError*y){[lock lock];reply=x;failure=y;count++;[lock unlock];dispatch_semaphore_signal(sem);};
  if(f==7)[library newFunctionWithName:name constantValues:values completionHandler:complete];else[library newFunctionWithDescriptor:descriptor completionHandler:complete];
  descriptor.name=@"mutated-after-request";
  if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return nil;
  [lock lock];function=reply;if(error)*error=failure;callbacks=count;[lock unlock];if(callbacks!=1)return nil;
 }
 NSString*wanted=f==6?[@"alias_" stringByAppendingString:name]:name;if(![function.name isEqual:wanted])return nil;
 if(callbackCount)*callbackCount=callbacks;return function;
}
static id<MTLFunction>nativeLibraryFunction(KPCPUICBScope*s,id<MTLDevice>d,NSString*path,NSString*name,NSString*route,BOOL tagged,NSError**error){
 NSArray*parts=[route componentsSeparatedByString:@":"];if(parts.count!=3)return nil;
 NSUInteger l=[parts[0]integerValue],f=[parts[1]integerValue],p=[parts[2]integerValue];
 if(l>2||f>8||p>5)return nil;
 NSData*source=[NSData dataWithContentsOfFile:path];NSMutableArray*names=[NSMutableArray new];for(NSString*n in @[@"basic",@"barrier",@"copy",@"no_seed",@"no_gather",@"no_finish"])[names addObject:[@"encode_dataflow_" stringByAppendingString:n]];
 if(![s registerNativeSourceCommandIRLibraryData:source expectedSHA256:hash(source)functionNames:names reusableContexts:tagged error:error])return nil;
 id<MTLLibrary>library=nil;
 if(l==0){dispatch_data_t bytes=dispatch_data_create(source.bytes,source.length,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{(void)source.length;});library=[d newLibraryWithData:bytes error:error];}
 else if(l==1)library=[d newLibraryWithURL:[NSURL fileURLWithPath:path]error:error];else library=[d newLibraryWithFile:path error:error];
 if(!library)return nil;nativeLibraryOwner=library;
 NSUInteger callbacks=0;id<MTLFunction>function=nativeSourceFunctionFromLibrary(library,name,f,error,&callbacks);if(!function)return nil;
 nativeLibraryReception=@{@"route":route,@"library_factory":@(l),@"function_factory":@(f),@"pipeline_factory":@(p),@"function_callbacks":@(callbacks),@"source_function":name,@"returned_function":function.name,@"generation_tagged_root":@(tagged),@"manual_function_registrations":@0,@"manual_compute_adaptations":@0};return function;
}
static id<MTLComputePipelineState>nativeLibraryPipeline(id<MTLDevice>d,id<MTLFunction>f,BOOL tagged,NSError**error){
 NSUInteger kind=[nativeLibraryReception[@"pipeline_factory"]unsignedIntegerValue];id<MTLComputePipelineState>pipeline=nil;MTLComputePipelineReflection*reflection=nil;NSUInteger callbacks=0;
 MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=f;p.label=@"native-source-library";MTLPipelineOption options=MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo;
 if(kind==0)pipeline=[d newComputePipelineStateWithFunction:f error:error];
 else if(kind==1)pipeline=[d newComputePipelineStateWithFunction:f options:options reflection:&reflection error:error];
 else if(kind==2)pipeline=[d newComputePipelineStateWithDescriptor:p options:options reflection:&reflection error:error];
 else{
  NSLock*lock=[NSLock new];__block id<MTLComputePipelineState>reply=nil;__block MTLComputePipelineReflection*info=nil;__block NSError*failure=nil;__block NSUInteger count=0;dispatch_semaphore_t sem=dispatch_semaphore_create(0);
  void(^complete)(id<MTLComputePipelineState>,MTLComputePipelineReflection*,NSError*)=^(id<MTLComputePipelineState>x,MTLComputePipelineReflection*y,NSError*z){[lock lock];reply=x;info=y;failure=z;count++;[lock unlock];dispatch_semaphore_signal(sem);};
  if(kind==3)[d newComputePipelineStateWithFunction:f completionHandler:^(id<MTLComputePipelineState>x,NSError*e){complete(x,nil,e);}];else if(kind==4)[d newComputePipelineStateWithFunction:f options:options completionHandler:complete];else[d newComputePipelineStateWithDescriptor:p options:options completionHandler:complete];
  if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return nil;
  [lock lock];pipeline=reply;reflection=info;if(error)*error=failure;callbacks=count;[lock unlock];if(callbacks!=1)return nil;
 }
 BOOL wants=kind!=0&&kind!=3;MTLArgument*root=reflection.arguments.firstObject;NSMutableArray*members=[NSMutableArray new];
 if(wants){if(root.bufferDataSize!=48||root.bufferAlignment!=8||root.bufferStructType.members.count!=6)return nil;for(NSUInteger i=0;i<6;i++){MTLStructMember*m=root.bufferStructType.members[i];if(m.offset!=i*8||m.argumentIndex!=i||m.dataType!=(i==0?(tagged?MTLDataTypeULong:MTLDataTypePointer):i==1?MTLDataTypeULong:MTLDataTypePointer))return nil;[members addObject:@{@"index":@(i),@"type":@(m.dataType),@"offset":@(m.offset)}];}}
 if(!pipeline||![NSStringFromClass(object_getClass(pipeline))isEqual:@"NVMTLComputePipelineState"]||pipeline.threadExecutionWidth!=32||pipeline.maxTotalThreadsPerThreadgroup<32||((kind==2||kind==5)&&![pipeline.label isEqual:@"native-source-library"]))return nil;
 NSMutableDictionary*receipt=[nativeLibraryReception mutableCopy];receipt[@"pipeline_callbacks"]=@(callbacks);receipt[@"native_reflection"]=@(wants);receipt[@"pipeline_members"]=members;receipt[@"pipeline_class"]=NSStringFromClass(object_getClass(pipeline));nativeLibraryReception=receipt;return pipeline;
}
