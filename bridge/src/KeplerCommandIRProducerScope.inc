// Included inside the scope implementation. No global/native class is patched.
- (BOOL)registerCommandIRProducerForFunction:(id<MTLFunction>)function carrierData:(NSData*)carrier programData:(NSData*)program error:(NSError**)error {
 if(error)*error=nil;
 KPIRFunctionLink*link=function?objc_getAssociatedObject(function,&IRFunctionKey):nil;
 if(_restored||!_GPUCommandIRv2Selector||!link||link.scope!=self||function.device!=_device||link.bindingCount!=4||link.bufferIndex!=0||link.nativeRootPipeline)return fail(error,@"Active, unregistered n4 producer function required");
 NSString*programPin=nativeProducerPins()[function.name];
 NSData*carrierSnapshot=carrier?[NSData dataWithBytes:carrier.bytes length:carrier.length]:nil;
 NSData*programSnapshot=program?[NSData dataWithBytes:program.bytes length:program.length]:nil;
 if(![link.librarySHA isEqual:@"a9367d4492cd100adfcde990efe0b043e4b070536a3615be5b9b2f63bfb473db"]||!programPin||
    ![hash(carrierSnapshot)isEqual:@"bf5065e2db01161839efe25eac67a2052fc3324367d3c4754182550857014574"]||
    ![hash(programSnapshot)isEqual:programPin])return fail(error,@"Producer source/carrier/program fingerprint differs");
 Class<KPCommandIRProducerFactoryProtocol>factory=(Class<KPCommandIRProducerFactoryProtocol>)NSClassFromString(@"KPCommandIRProducerFactory");
 if(!factory)return fail(error,@"Optional native producer factory module is not linked");
 NSDictionary*proof=nil;id<MTLComputePipelineState>pipeline=nil;
 @try{pipeline=[factory newPipelineForDevice:_device carrier:carrierSnapshot program:programSnapshot error:error evidence:&proof];}
 @catch(NSException*x){return fail(error,x.reason?:@"Native producer construction failed");}
 if(!pipeline||pipeline.device!=_device||pipeline.threadExecutionWidth!=32||pipeline.maxTotalThreadsPerThreadgroup<32||![proof[@"contract_verified"]boolValue]||[proof[@"rejected_import"]boolValue])return fail(error,@"Native producer import/limits differ");
 Class dynamic=object_getClass(_device);
 {std::lock_guard<std::mutex>lock(installMutex);
  const SEL selectors[]={@selector(newComputePipelineStateWithFunction:error:),@selector(newComputePipelineStateWithFunction:options:reflection:error:),@selector(newComputePipelineStateWithDescriptor:options:reflection:error:),@selector(newComputePipelineStateWithFunction:completionHandler:),@selector(newComputePipelineStateWithFunction:options:completionHandler:),@selector(newComputePipelineStateWithDescriptor:options:completionHandler:)};
  const IMP implementations[]={(IMP)registeredProducerPipeline,(IMP)producerFunctionOptions,(IMP)producerDescriptor,(IMP)producerFunctionAsync,(IMP)producerFunctionAsyncOptions,(IMP)producerDescriptorAsync};
  for(unsigned i=0;i<6;i++)if(!installRenderOverride(dynamic,_originalDeviceClass,selectors[i],implementations[i]))return fail(error,@"Cannot install device-local pipeline factory variants");
 }
 link.nativeProducerCarrier=carrierSnapshot;link.nativeProducerProgram=programSnapshot;
 link.nativeRootPipeline=pipeline;
 link.nativeProducerProfile=@{@"function":function.name,@"source_SHA256":link.librarySHA,@"carrier_SHA256":hash(carrierSnapshot),@"program_SHA256":programPin,@"import":proof};
 [_eventRows addObject:@{@"operation":@"register_IRv2_native_producer",@"profile":link.nativeProducerProfile,@"native_pipeline":@YES,@"source_compiler_replaced":@NO,@"host_push_buffer_required":@NO,@"GPU_execution":@NO}];
 return YES;
}
