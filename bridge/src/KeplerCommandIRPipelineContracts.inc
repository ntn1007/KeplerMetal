// Public API variants for the same explicitly registered source/program set.
// Reflection objects are fresh adapters around native function metadata; they
// are never cached on the function (which could form a metadata ownership cycle).
namespace {
KPIRFunctionLink*producerLink(id device,id<MTLFunction>function){
 KPCPUICBScope*s=((KPScopeLink*)objc_getAssociatedObject(device,&contextKey)).scope;
 KPIRFunctionLink*link=function?objc_getAssociatedObject(function,&IRFunctionKey):nil;
 return s&&!s.restored&&link.scope==s&&link.nativeRootPipeline?link:nil;
}
Class originalProducerDevice(id device){KPCPUICBScope*s=((KPScopeLink*)objc_getAssociatedObject(device,&contextKey)).scope;return s?s.originalDeviceClass:class_getSuperclass(object_getClass(device));}
void producerRequest(KPIRFunctionLink*link,SEL selector,MTLPipelineOption options){
 KPCPUICBScope*s=link.scope;if(!s)return;NSMutableArray*rows=s.eventRows;
 @synchronized(rows){[rows addObject:@{@"operation":@"IRv2_pipeline_contract_request",@"selector":NSStringFromSelector(selector),@"options":@(options)}];}
}
BOOL prepareProducerReflection(id<MTLFunction>function,KPIRFunctionLink*link,MTLPipelineOption options,MTLComputePipelineReflection*__autoreleasing*reflection,NSError**error){
 if(error)*error=nil;if(reflection)*reflection=nil;
 if(options&~MTLPipelineOption(3))return fail(error,@"Binary archive/unknown pipeline options are outside this producer contract");
 if(!options||!reflection)return YES;
 MTLArgument*root=nil;id<MTLArgumentEncoder>native=nil;
 @try{native=nativeFunctionEncoder(function,@selector(newArgumentEncoderWithBufferIndex:reflection:),link.bufferIndex,&root);}
 @catch(NSException*x){return fail(error,x.reason?:@"Native reflection unavailable");}
 if(![functionArgumentSchema(root,native,link.bufferIndex)isEqual:link.schema])return fail(error,@"Native producer reflection changed");
 KPIRComputeReflection*value=[[KPIRComputeReflection alloc]initWithNativeArgument:root];
 if(!value||value.arguments.count!=1||value.bindings.count!=1)return fail(error,@"Reflection adapter construction failed");
 *reflection=value;return YES;
}
BOOL producerDescriptorSupported(MTLComputePipelineDescriptor*d,NSError**error){
 @try{
  if(d.stageInputDescriptor)for(NSUInteger i=0;i<31;i++)if(d.stageInputDescriptor.attributes[i].format!=MTLAttributeFormatInvalid)return fail(error,@"Active stage-in attributes are not qualified for this producer");
  if(d.supportIndirectCommandBuffers||d.supportAddingBinaryFunctions||d.maxCallStackDepth!=1)return fail(error,@"Indirect/binary/call-stack descriptor features are not qualified");
  if(([d respondsToSelector:@selector(shaderValidation)]&&d.shaderValidation!=MTLShaderValidationDefault)||
     ([d respondsToSelector:@selector(preloadedLibraries)]&&d.preloadedLibraries.count)||d.insertLibraries.count||d.binaryArchives.count)return fail(error,@"Dynamic/validation/archive descriptor features are not qualified");
  if([d respondsToSelector:@selector(requiredThreadsPerThreadgroup)]){MTLSize required=d.requiredThreadsPerThreadgroup;if(required.width||required.height||required.depth)return fail(error,@"Required producer threadgroup geometry is not qualified");}
  if(d.maxTotalThreadsPerThreadgroup&&(d.maxTotalThreadsPerThreadgroup<32||d.maxTotalThreadsPerThreadgroup>1024))return fail(error,@"Producer thread limit must fit the qualified 32-thread dispatch and Kepler maximum");
  MTLLinkedFunctions*f=d.linkedFunctions;if(f.functions.count||f.binaryFunctions.count||f.privateFunctions.count||f.groups.count)return fail(error,@"Linked producer functions are not implemented");
  for(NSUInteger i=0;i<31;i++){MTLMutability m=d.buffers[i].mutability;if(m>MTLMutabilityImmutable||(i&&m!=MTLMutabilityDefault))return fail(error,@"Descriptor buffer mutability differs from the one-root ABI");}
 }@catch(NSException*x){return fail(error,x.reason?:@"Descriptor properties unavailable");}
 return YES;
}
id<MTLComputePipelineState>constructProducerDescriptor(id<MTLDevice>device,NSData*carrier,NSData*program,MTLComputePipelineDescriptor*descriptor,NSError**error) NS_RETURNS_RETAINED;
id<MTLComputePipelineState>constructProducerDescriptor(id<MTLDevice>device,NSData*carrier,NSData*program,MTLComputePipelineDescriptor*descriptor,NSError**error){
 Class<KPCommandIRProducerFactoryProtocol>factory=(Class<KPCommandIRProducerFactoryProtocol>)NSClassFromString(@"KPCommandIRProducerFactory");NSDictionary*proof=nil;id<MTLComputePipelineState>pipeline=nil;
 @try{pipeline=[factory newPipelineForDevice:device carrier:carrier program:program descriptor:descriptor error:error evidence:&proof];}@catch(NSException*x){fail(error,x.reason?:@"Descriptor producer import failed");return nil;}
 if(pipeline&&[proof[@"contract_verified"]boolValue]&&!configureNativeProducerThreadLimit(pipeline,descriptor.maxTotalThreadsPerThreadgroup,error))return nil;
 if(!pipeline||![proof[@"contract_verified"]boolValue]||pipeline.device!=device||pipeline.threadExecutionWidth!=32||pipeline.maxTotalThreadsPerThreadgroup<32||
    (descriptor.maxTotalThreadsPerThreadgroup&&pipeline.maxTotalThreadsPerThreadgroup>descriptor.maxTotalThreadsPerThreadgroup)||
    (descriptor.label&&![pipeline.label isEqual:descriptor.label])){fail(error,@"Native descriptor pipeline limits/label/import differ");return nil;}
 return pipeline;
}
id<MTLComputePipelineState>producerFunctionOptions(id self,SEL selector,id<MTLFunction>function,MTLPipelineOption options,MTLComputePipelineReflection*__autoreleasing*reflection,NSError**error) NS_RETURNS_RETAINED;
id<MTLComputePipelineState>producerFunctionOptions(id self,SEL selector,id<MTLFunction>function,MTLPipelineOption options,MTLComputePipelineReflection*__autoreleasing*reflection,NSError**error){
 KPIRFunctionLink*link=producerLink(self,function);
 if(!link){typedef id<MTLComputePipelineState>(*F)(id,SEL,id<MTLFunction>,MTLPipelineOption,MTLComputePipelineReflection*__autoreleasing*,NSError**)__attribute__((ns_returns_retained));return((F)class_getMethodImplementation(originalProducerDevice(self),selector))(self,selector,function,options,reflection,error);}
 producerRequest(link,selector,options);if(!prepareProducerReflection(function,link,options,reflection,error))return nil;return link.nativeRootPipeline;
}
id<MTLComputePipelineState>producerDescriptor(id self,SEL selector,MTLComputePipelineDescriptor*descriptor,MTLPipelineOption options,MTLComputePipelineReflection*__autoreleasing*reflection,NSError**error) NS_RETURNS_RETAINED;
id<MTLComputePipelineState>producerDescriptor(id self,SEL selector,MTLComputePipelineDescriptor*descriptor,MTLPipelineOption options,MTLComputePipelineReflection*__autoreleasing*reflection,NSError**error){
 MTLComputePipelineDescriptor*snapshot=[descriptor copy];KPIRFunctionLink*link=producerLink(self,snapshot.computeFunction);
 if(!link){typedef id<MTLComputePipelineState>(*F)(id,SEL,MTLComputePipelineDescriptor*,MTLPipelineOption,MTLComputePipelineReflection*__autoreleasing*,NSError**)__attribute__((ns_returns_retained));return((F)class_getMethodImplementation(originalProducerDevice(self),selector))(self,selector,descriptor,options,reflection,error);}
 if(error)*error=nil;if(reflection)*reflection=nil;producerRequest(link,selector,options);
 if(!producerDescriptorSupported(snapshot,error))return nil;MTLComputePipelineReflection*value=nil;if(!prepareProducerReflection(snapshot.computeFunction,link,options,&value,error))return nil;
 id<MTLComputePipelineState>pipeline=constructProducerDescriptor(self,link.nativeProducerCarrier,link.nativeProducerProgram,snapshot,error);if(pipeline&&reflection)*reflection=value;return pipeline;
}
void producerFunctionAsyncOptions(id self,SEL selector,id<MTLFunction>function,MTLPipelineOption options,MTLNewComputePipelineStateWithReflectionCompletionHandler completion){
 KPIRFunctionLink*link=producerLink(self,function);
 if(!link){typedef void(*F)(id,SEL,id<MTLFunction>,MTLPipelineOption,MTLNewComputePipelineStateWithReflectionCompletionHandler);((F)class_getMethodImplementation(originalProducerDevice(self),selector))(self,selector,function,options,completion);return;}
 if(!completion)reject(@"Completion handler is required");producerRequest(link,selector,options);
 NSError*error=nil;MTLComputePipelineReflection*reflection=nil;BOOL ok=prepareProducerReflection(function,link,options,&reflection,&error);id<MTLComputePipelineState>pipeline=ok?link.nativeRootPipeline:nil;
 dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{completion(pipeline,reflection,error);});
}
void producerFunctionAsync(id self,SEL selector,id<MTLFunction>function,MTLNewComputePipelineStateCompletionHandler completion){
 KPIRFunctionLink*link=producerLink(self,function);
 if(!link){typedef void(*F)(id,SEL,id<MTLFunction>,MTLNewComputePipelineStateCompletionHandler);((F)class_getMethodImplementation(originalProducerDevice(self),selector))(self,selector,function,completion);return;}
 if(!completion)reject(@"Completion handler is required");producerRequest(link,selector,MTLPipelineOptionNone);id<MTLComputePipelineState>pipeline=link.nativeRootPipeline;
 dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{completion(pipeline,nil);});
}
void producerDescriptorAsync(id self,SEL selector,MTLComputePipelineDescriptor*descriptor,MTLPipelineOption options,MTLNewComputePipelineStateWithReflectionCompletionHandler completion){
 MTLComputePipelineDescriptor*snapshot=[descriptor copy];KPIRFunctionLink*link=producerLink(self,snapshot.computeFunction);
 if(!link){typedef void(*F)(id,SEL,MTLComputePipelineDescriptor*,MTLPipelineOption,MTLNewComputePipelineStateWithReflectionCompletionHandler);((F)class_getMethodImplementation(originalProducerDevice(self),selector))(self,selector,descriptor,options,completion);return;}
 if(!completion)reject(@"Completion handler is required");producerRequest(link,selector,options);
 NSError*error=nil;MTLComputePipelineReflection*reflection=nil;BOOL ok=producerDescriptorSupported(snapshot,&error)&&prepareProducerReflection(snapshot.computeFunction,link,options,&reflection,&error);
 NSData*carrier=link.nativeProducerCarrier,*program=link.nativeProducerProgram;id<MTLDevice>device=self;
 dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{@autoreleasepool{NSError*failure=error;id<MTLComputePipelineState>pipeline=ok?constructProducerDescriptor(device,carrier,program,snapshot,&failure):nil;completion(pipeline,pipeline?reflection:nil,failure);}});
}
}
