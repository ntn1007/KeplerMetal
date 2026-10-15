// Included within KPCPUICBScope's implementation.
- (id<MTLFunction>)newCommandIRFunctionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected functionName:(NSString*)name rootBufferIndex:(NSUInteger)index error:(NSError**)error {
 expected=[expected copy];name=[name copy];
 if(_restored||!_GPUCommandIRv2Selector||index!=0||!name.length||!data.length||!digestString(expected)){fail(error,@"An active IRv2 scope and root buffer0 are required");return nil;}
 NSData*snapshot=[NSData dataWithBytes:data.bytes length:data.length];if(![hash(snapshot)isEqual:expected]){fail(error,@"Producer library SHA256 differs");return nil;}
 id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);if(!library)return nil;id<MTLFunction>function=[library newFunctionWithName:name];
 if(!function||function.functionType!=MTLFunctionTypeKernel||function.device!=_device||objc_getAssociatedObject(function,&IRFunctionKey)){fail(error,@"Native producer function identity/type differs");return nil;}
 MTLArgument*argument=nil;id<MTLArgumentEncoder>native=nil;
 @try{native=[function newArgumentEncoderWithBufferIndex:index reflection:&argument];}
 @catch(NSException*x){fail(error,x.reason?:@"Native argument reflection failed");return nil;}
 NSDictionary*schema=functionArgumentSchema(argument,native,index);
 if(!schema){fail(error,@"Native reflection is outside the dense IRv2 ICB/pipeline/pointer ABI");return nil;}
 BOOL gettersAdapted=![native isKindOfClass:KPCommandIRArgumentEncoder.class];
 Class original=object_getClass(function),dynamic=original;
 if(gettersAdapted){
 {std::lock_guard<std::mutex>lock(installMutex);dynamic=scopedClass(functionClasses,original,@"KPIRFunction_",@selector(newArgumentEncoderWithBufferIndex:),(IMP)functionIRArguments,error);if(!dynamic||!installRenderOverride(dynamic,original,@selector(newArgumentEncoderWithBufferIndex:reflection:),(IMP)functionIRArgumentsWithReflection)){fail(error,@"Cannot create function-local encoder overrides");return nil;}}
 KPIRFunctionLink*link=[KPIRFunctionLink new];link.scope=self;link.originalClass=original;link.bufferIndex=index;link.bindingCount=[schema[@"binding_count"]unsignedIntegerValue];link.schema=schema;
 objc_setAssociatedObject(function,&IRFunctionKey,link,OBJC_ASSOCIATION_RETAIN_NONATOMIC);object_setClass(function,dynamic);
 KPAdaptedFunction*record=[KPAdaptedFunction new];record.function=function;record.originalClass=original;if(!_adaptedFunctions)_adaptedFunctions=[NSMutableArray new];[_adaptedFunctions addObject:record];
 }
 if(!_functionLibraries)_functionLibraries=[NSMutableArray new];[_functionLibraries addObject:@{@"library":library,@"bytes":snapshot}];
 [_eventRows addObject:@{@"operation":@"register_native_IRv2_function",@"function":name,@"library_SHA256":expected,@"schema":schema,@"native_class":NSStringFromClass(original),@"dynamic_class":NSStringFromClass(dynamic),@"native_reflection_reused":@YES,@"function_getters_adapted":@(gettersAdapted),@"native_argument_encoder_class":NSStringFromClass(object_getClass(native)),@"native_shader_compilation_replaced":@NO,@"GPU_execution":@NO}];
 return function;
}
