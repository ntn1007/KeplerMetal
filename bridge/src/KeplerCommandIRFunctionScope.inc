// Included within KPCPUICBScope's implementation.
- (id<MTLFunction>)newCommandIRFunctionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected functionName:(NSString*)name rootBufferIndex:(NSUInteger)index error:(NSError**)error {
 expected=[expected copy];name=[name copy];
 if(_restored||!_GPUCommandIRv2Selector||index||!name.length||!data.length||!digestString(expected)){fail(error,@"An active IRv2 scope and root buffer0 are required");return nil;}
 NSData*snapshot=[NSData dataWithBytes:data.bytes length:data.length];if(![hash(snapshot)isEqual:expected]){fail(error,@"Producer library SHA256 differs");return nil;}
 id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);if(!library)return nil;id<MTLFunction>function=[library newFunctionWithName:name];
 if(!adoptNativeIRFunction(self,function,expected,index,YES,error))return nil;
 @synchronized(_factoryLock){if(!_functionLibraries)_functionLibraries=[NSMutableArray new];[_functionLibraries addObject:@{@"library":library,@"bytes":snapshot}];}return function;
}
