// Included within KPCPUICBScope's implementation.
- (id<MTLFunction>)newCommandIRFunctionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected functionName:(NSString*)name rootBufferIndex:(NSUInteger)index error:(NSError**)error {
 expected=[expected copy];name=[name copy];
 if(_restored||!_GPUCommandIRv2Selector||index||!name.length||!data.length||!digestString(expected)){fail(error,@"An active IRv2 scope and root buffer0 are required");return nil;}
 NSData*snapshot=[NSData dataWithBytes:data.bytes length:data.length];if(![hash(snapshot)isEqual:expected]){fail(error,@"Producer library SHA256 differs");return nil;}
 id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);if(!library)return nil;id<MTLFunction>function=[library newFunctionWithName:name];
 if(!adoptNativeIRFunction(self,function,expected,index,YES,error))return nil;
 @synchronized(_factoryLock){if(!_functionLibraries)_functionLibraries=[NSMutableArray new];[_functionLibraries addObject:@{@"library":library,@"bytes":snapshot}];}return function;
}

// The caller selects the source-lowered CommandIR ABI explicitly. Native
// function and pipeline compilation remain untouched; only the two argument
// encoder getters receive the existing bounded resource/ownership adapter.
- (id<MTLFunction>)newNativeSourceCommandIRFunctionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected functionName:(NSString*)name rootBufferIndex:(NSUInteger)index error:(NSError**)error {
 @synchronized(_factoryLock){
 expected=[expected copy];name=[name copy];if(error)*error=nil;
 if(_restored||!_GPUCommandIRv2Selector||index||!name.length||![data isKindOfClass:NSData.class]||!data.length||!digestString(expected)){fail(error,@"An active source-lowered IRv2 scope and root buffer0 are required");return nil;}
 NSData*snapshot=[NSData dataWithBytes:data.bytes length:data.length];if(![hash(snapshot)isEqual:expected]){fail(error,@"Source-lowered producer library SHA256 differs");return nil;}
 id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);if(!library)return nil;id<MTLFunction>function=[library newFunctionWithName:name];
 if(!adoptNativeIRFunction(self,function,expected,index,NO,error,YES))return nil;
 @synchronized(_factoryLock){
  if(!_functionLibraries)_functionLibraries=[NSMutableArray new];[_functionLibraries addObject:@{@"library":library,@"bytes":snapshot}];
  [_eventRows addObject:@{@"operation":@"register_native_source_IRv2_function",@"function":function.name,@"library_SHA256":expected,@"schema":((KPIRFunctionLink*)objc_getAssociatedObject(function,&IRFunctionKey)).schema,@"instruction_import":@NO,@"native_pipeline_factories_preserved":@YES,@"Apple_ICB_identity":@NO,@"GPU_execution":@NO}];
 }
 return function;
 }
}
