// SPDX-License-Identifier: MIT
// One registration, followed by ordinary native library/function calls.
- (BOOL)registerCommandIRLibraryData:(NSData*)data expectedSHA256:(NSString*)expected carrierData:(NSData*)carrier programsByFunction:(NSDictionary<NSString*,NSData*>*)programs error:(NSError**)error {
 if(error)*error=nil;expected=[expected copy];
 if(_restored||!_GPUCommandIRv2Selector||![data isKindOfClass:NSData.class]||![carrier isKindOfClass:NSData.class]||![programs isKindOfClass:NSDictionary.class]||![expected isEqual:@"a9367d4492cd100adfcde990efe0b043e4b070536a3615be5b9b2f63bfb473db"])return fail(error,@"Active IRv2 scope and the pinned producer library are required");
 NSData*source=[NSData dataWithBytes:data.bytes length:data.length],*carrierSnapshot=[NSData dataWithBytes:carrier.bytes length:carrier.length];NSDictionary*pins=nativeProducerPins();
 if(![hash(source)isEqual:expected]||![hash(carrierSnapshot)isEqual:@"bf5065e2db01161839efe25eac67a2052fc3324367d3c4754182550857014574"]||![[NSSet setWithArray:programs.allKeys]isEqual:[NSSet setWithArray:pins.allKeys]])return fail(error,@"Library/carrier/program set fingerprints differ");
 NSMutableDictionary*snapshots=[NSMutableDictionary new];for(NSString*name in pins){NSData*input=programs[name];if(![input isKindOfClass:NSData.class])return fail(error,@"Program data missing");NSData*copy=[NSData dataWithBytes:input.bytes length:input.length];if(![hash(copy)isEqual:pins[name]])return fail(error,@"Program fingerprint differs");snapshots[name]=copy;}
 @synchronized(_factoryLock){if(_restored||_registeredIRLibraries[expected])return fail(error,@"Library registration is inactive or already present");}
 Class<KPCommandIRProducerFactoryProtocol>factory=(Class<KPCommandIRProducerFactoryProtocol>)NSClassFromString(@"KPCommandIRProducerFactory");if(!factory)return fail(error,@"Native producer module is not linked");
 id<MTLLibrary>library=libraryFromSnapshot(_device,source,error);if(!library)return NO;NSMutableDictionary*profiles=[NSMutableDictionary new];
 for(NSString*name in [pins.allKeys sortedArrayUsingSelector:@selector(compare:)]){
  id<MTLFunction>function=[library newFunctionWithName:name];if(!function||function.functionType!=MTLFunctionTypeKernel||function.device!=_device||function.functionConstantsDictionary.count)return fail(error,@"Native producer declaration differs");
  MTLArgument*root=nil;id<MTLArgumentEncoder>native=nil;nativeFunctionArgumentDepth++;@try{native=[function newArgumentEncoderWithBufferIndex:0 reflection:&root];}@catch(NSException*x){fail(error,x.reason?:@"Native producer reflection failed");}@finally{nativeFunctionArgumentDepth--;}
  NSDictionary*schema=functionArgumentSchema(root,native,0);if([schema[@"binding_count"]unsignedIntegerValue]!=4)return fail(error,@"Library producer root schema differs");
  NSDictionary*proof=nil;id<MTLComputePipelineState>pipeline=[factory newPipelineForDevice:_device carrier:carrierSnapshot program:snapshots[name]error:error evidence:&proof];
  if(!pipeline||pipeline.device!=_device||pipeline.threadExecutionWidth!=32||pipeline.maxTotalThreadsPerThreadgroup<32||![proof[@"contract_verified"]boolValue]||[proof[@"rejected_import"]boolValue])return fail(error,@"Library producer import/limits differ");
  NSDictionary*profile=@{@"function":name,@"source_SHA256":expected,@"carrier_SHA256":hash(carrierSnapshot),@"program_SHA256":pins[name],@"import":proof};profiles[name]=@{@"schema":schema,@"pipeline":pipeline,@"program":snapshots[name],@"profile":profile};
 }
 NSDictionary*registration=@{@"source_SHA256":expected,@"source_bytes":source,@"carrier":carrierSnapshot,@"functions":[profiles copy]};
 @synchronized(_factoryLock){
  if(_restored||_registeredIRLibraries[expected])return fail(error,@"Library registration changed while preparing immutable profiles");
  if(!installIRLibraryFactories(self,error)||!enableAutomaticComputeFactories(self,error))return NO;
  if(!_registeredIRLibraries)_registeredIRLibraries=[NSMutableDictionary new];_registeredIRLibraries[expected]=registration;
  libraryEvent(self,@{@"operation":@"register_IRv2_library",@"source_SHA256":expected,@"functions":[pins.allKeys sortedArrayUsingSelector:@selector(compare:)],@"prepared_native_pipelines":@6,@"source_function_constants":@0,@"GPU_execution":@NO});return YES;
 }
}
