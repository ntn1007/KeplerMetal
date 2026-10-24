// Included inside KPCPUICBScope. No system classes or installed files changed.
- (BOOL)enableGPUCommandIRv2WithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
 NSString*pin=@"a16652f21d39de58e16dbb4704b98813565b5ec3e9e2f0f926c0eb6d77015997";
 NSData*snapshot=data?[NSData dataWithBytes:data.bytes length:data.length]:nil;
 if(_restored||!_GPUBindingSelector||![expected isEqual:pin]||!snapshot||![hash(snapshot)isEqual:pin])return fail(error,@"Command IR v2 materializer identity/scope differs");
 if(_GPUCommandIRv2Library)return YES;
 id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);if(!library)return NO;
 id<MTLComputePipelineState>p=[_device newComputePipelineStateWithFunction:[library newFunctionWithName:@"materialize_compute_command_ir_v2"]error:error];
 if(!p||p.threadExecutionWidth!=32||p.maxTotalThreadsPerThreadgroup<64)return fail(error,@"Command IR v2 materializer limits differ");
 {std::lock_guard<std::mutex>lock(installMutex);if(!installRenderOverride(object_getClass(_device),_originalDeviceClass,@selector(newArgumentEncoderWithArguments:),(IMP)createIRArgumentEncoder))return fail(error,@"Cannot install scoped argument-encoder factory");}
 _GPUCommandIRv2Library=library;_GPUCommandIRv2Selector=p;[_eventRows addObject:@{@"operation":@"enable_GPU_command_IR_v2",@"library_SHA256":pin}];return YES;
}
- (KPGPUCommandSelection*)newGPUCommandIRv2FromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources records:(id<MTLBuffer>)records recordOffset:(NSUInteger)offset error:(NSError**)error {
 return[self newGPUCommandIRv2FromBuffer:source sourceRange:range destination:destination destinationRange:targetRange resources:resources records:records recordOffset:offset stablePipelineIdentities:NO error:error];
}
- (KPGPUCommandSelection*)newGPUStableCommandIRFromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources records:(id<MTLBuffer>)records recordOffset:(NSUInteger)offset error:(NSError**)error {
 if(_restored){fail(error,@"Stable command scope was restored");return nil;}
 return[self newGPUCommandIRv2FromBuffer:source sourceRange:range destination:destination destinationRange:targetRange resources:resources records:records recordOffset:offset stablePipelineIdentities:YES error:error];
}
- (uint64_t)commandIRIdentityForPipeline:(id<MTLComputePipelineState>)pipeline error:(NSError**)error {
 @synchronized(_factoryLock){
  if(error)*error=nil;
  if(_restored||!_GPUCommandIRv2Selector||![[self profileForPipeline:pipeline][@"native_registration_v1"]boolValue]){fail(error,@"Stable pipeline identity requires an active owned native profile");return 0;}
  NSValue*key=[NSValue valueWithPointer:(__bridge const void*)pipeline];NSNumber*old=_stablePipelineIdentities[key];if(old)return old.unsignedLongLongValue;
  uint64_t value=allocateStablePipelineIdentity();if(!value){fail(error,@"Stable pipeline identity namespace exhausted");return 0;}
  if(!_stablePipelineIdentities)_stablePipelineIdentities=[NSMutableDictionary new];_stablePipelineIdentities[key]=@(value);
  [_eventRows addObject:@{@"operation":@"assign_stable_IR_pipeline_identity",@"identity":@(value),@"function":[self profileForPipeline:pipeline][@"function"],@"Apple_resource_ID":@NO}];return value;
 }
}
- (KPGPUCommandSelection*)newGPUCommandIRv2FromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources records:(id<MTLBuffer>)records recordOffset:(NSUInteger)offset stablePipelineIdentities:(BOOL)stable error:(NSError**)error {
 return[self newGPUCommandIRv2FromBuffer:source sourceRange:range destination:destination destinationRange:targetRange resources:resources records:records recordOffset:offset stablePipelineIdentities:stable reusable:nil generation:0 error:error];
}
- (KPGPUCommandSelection*)newGPUReusableCommandIRFromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources records:(id<MTLBuffer>)records recordOffset:(NSUInteger)offset error:(NSError**)error {
 if(error)*error=nil;
 if(_restored||!_GPUCommandIRv2Selector||![destination isKindOfClass:KPComputeICB.class]||[destination isKindOfClass:KPRenderICB.class]||((KPComputeICB*)destination).scope!=self){fail(error,@"Reusable ICB scope/domain differs");return nil;}
 KPComputeICB*d=(KPComputeICB*)destination;KPReusableIRContext*storage=d.reusableContext;
 if(!storage){storage=[KPReusableIRContext new];storage.queue=_queue;storage.buffer=[_device newBufferWithLength:sizeof(KPStableCommandContext)options:MTLResourceStorageModePrivate];uint64_t a=storage.buffer.gpuAddress;if(!a||a>>40||storage.buffer.length>((uint64_t(1)<<40)-a)){fail(error,@"Reusable context address span differs");return nil;}d.reusableContext=storage;}
 uint32_t generation=0;
 @synchronized(storage){
  if(![storage idle:error])return nil;
  if(!storage.retired){fail(error,@"Reset the prior reusable generation before preparing another");return nil;}
  generation=allocateContextGeneration();if(!generation){fail(error,@"Reusable context generation namespace exhausted");return nil;}
  storage.preparing=YES;
 }
 KPGPUCommandSelection*plan=nil;
 @try{plan=[self newGPUCommandIRv2FromBuffer:source sourceRange:range destination:destination destinationRange:targetRange resources:resources records:records recordOffset:offset stablePipelineIdentities:YES reusable:storage generation:generation error:error];}
 @finally{@synchronized(storage){storage.preparing=NO;}}
 if(!plan)return nil;
 @synchronized(storage){
  if(storage.poisoned){fail(error,@"Reusable context was poisoned during preparation");return nil;}
  storage.generation=generation;storage.retired=NO;storage.plan=plan;storage.resources=plan.commandIRProducerResources;
  for(KPComputeICBCommand*c in plan.targetCommands){c.reusableContext=storage;c.reusableGeneration=generation;}
 }
 [plan.eventRows addObject:@{@"operation":@"prepare_reusable_IR_context",@"generation":@(generation),@"context_GPU_address":@(storage.buffer.gpuAddress),@"generation_tag_shift":@40}];return plan;
}
- (KPGPUCommandSelection*)newGPUCommandIRv2FromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources records:(id<MTLBuffer>)records recordOffset:(NSUInteger)offset stablePipelineIdentities:(BOOL)stable reusable:(KPReusableIRContext*)reusable generation:(uint32_t)generation error:(NSError**)error {
 if(!_GPUCommandIRv2Selector||!resources.count||resources.count>4||![records conformsToProtocol:@protocol(MTLBuffer)]||records.storageMode!=MTLStorageModePrivate||records.device!=_device){fail(error,@"IR v2 resources/records/scope differ");return nil;}
 if(![source isKindOfClass:KPComputeICB.class]||![destination isKindOfClass:KPComputeICB.class]||[source isKindOfClass:KPRenderICB.class]||[destination isKindOfClass:KPRenderICB.class]){fail(error,@"IR v2 command domain differs");return nil;}
 KPComputeICB*s=(KPComputeICB*)source,*d=(KPComputeICB*)destination;
 if(d.reusableContext&&!reusable){fail(error,@"A reusable ICB requires its generation-aware constructor");return nil;}
 KPCommandIRArgumentContext*prior=d.commandIRArgumentContext;KPGPUCommandSelection*priorPlan=prior.plan;
 if(prior.roots.count&&priorPlan&&priorPlan.selectionBuffer.status!=MTLCommandBufferStatusCompleted&&!(reusable&&priorPlan.reusableContext==reusable&&reusable.retired)){fail(error,@"An exported argument context still owns the target ICB");return nil;}
 if(s.scope!=self||d.scope!=self||!range.length||range.length>8||range.location>s.size||range.length>s.size-range.location||!targetRange.length||targetRange.length>8||targetRange.location>d.size||targetRange.length>d.size-targetRange.location){fail(error,@"IR v2 scope/ranges differ");return nil;}
 NSMutableArray*blocked=[NSMutableArray arrayWithObject:records];NSMutableArray<KPComputeICBCommand*>*sourceCommands=[NSMutableArray new];NSUInteger n=0,constantIndex=NSNotFound;
 uint64_t ra=records.gpuAddress;if(!ra||ra>>40||records.length>((uint64_t(1)<<40)-ra)){fail(error,@"IR v2 record address span differs");return nil;}
 for(unsigned pass=0;pass<2;pass++){KPComputeICB*icb=pass?d:s;NSRange r=pass?targetRange:range;
  for(NSUInteger i=r.location;i<NSMaxRange(r);i++){
   KPComputeICBCommand*c=icb.commands[i];NSDictionary*p=[self profileForPipeline:c.pipeline];NSUInteger count=0,mask=0,constant=[p[@"constant_buffer_index"]unsignedIntegerValue];
   for(NSDictionary*a in p[@"reflection"])if([a[@"type"]unsignedIntegerValue]==MTLArgumentTypeBuffer){NSUInteger index=[a[@"index"]unsignedIntegerValue];if(index>=4){fail(error,@"IR v2 reflected slot exceeds four");return nil;}count=MAX(count,index+1);mask|=1u<<index;}
   if(![p[@"native_registration_v1"]boolValue]||![p[@"binding_layout_v2"]boolValue]||(count!=3&&count!=4)||mask!=((1u<<count)-1u)||constant>=count||!p[@"binding_specs"][@(constant)]||(n&&n!=count)||(constantIndex!=NSNotFound&&constantIndex!=constant)||!c.hasDispatch||!c.record.residentDescriptorReady||c.residentOwners.count){fail(error,@"IR v2 requires original reflected3/4-slot templates with a common constants position");return nil;}n=count;constantIndex=constant;
   if(residentBindingError(c,self)){fail(error,@"IR v2 retained binding/grid state differs");return nil;}
   [blocked addObjectsFromArray:@[c.record.constants,c.record.descriptor]];for(NSDictionary*b in c.bindings.allValues)[blocked addObject:b[@"buffer"]];if(!pass)[sourceCommands addObject:c];
  }
 }
 // Only entry0 is the input itself. Later identical objects are protected
 // native state/bindings and must be rejected as aliases, not skipped.
 for(NSUInteger i=1;i<blocked.count;i++){id<MTLBuffer>b=blocked[i];uint64_t a=b.gpuAddress;if(ra<a+b.length&&a<ra+records.length){fail(error,@"IR v2 records alias retained native state/binding");return nil;}}
 NSMutableArray*owners=[NSMutableArray new],*catalogueUses=[NSMutableArray new];NSMutableData*addresses=[NSMutableData dataWithLength:resources.count*32];
 for(NSUInteger k=0;k<resources.count;k++){
  NSDictionary*entry=resources[k];if(![entry isKindOfClass:NSDictionary.class]){fail(error,@"IR v2 resource catalogue entry type differs");return nil;}NSArray*bindings=entry[@"bindings"];if(entry.count!=1||![bindings isKindOfClass:NSArray.class]||bindings.count!=n-1){fail(error,@"IR v2 resource catalogue shape differs");return nil;}
  for(NSUInteger i=0;i<bindings.count;i++){
   NSDictionary*b=bindings[i];if(![b isKindOfClass:NSDictionary.class]||b.count!=2||![b[@"offset"]isKindOfClass:NSNumber.class]||![b[@"buffer"]conformsToProtocol:@protocol(MTLBuffer)]){fail(error,@"IR v2 resource binding shape differs");return nil;}
   id<MTLBuffer>buffer=b[@"buffer"];NSUInteger off=[b[@"offset"]unsignedIntegerValue];uint64_t a=buffer.gpuAddress;
   if(buffer.device!=_device||buffer.storageMode!=MTLStorageModePrivate||off>buffer.length||!a||a>>40||buffer.length>((uint64_t(1)<<40)-a)){fail(error,@"IR v2 resource buffer/address span differs");return nil;}
   NSUInteger slot=i<constantIndex?i:i+1;
   for(KPComputeICBCommand*c in sourceCommands){NSDictionary*spec=[self profileForPipeline:c.pipeline][@"binding_specs"][@(slot)];if(!spec)continue;NSUInteger align=[spec[@"alignment"]unsignedIntegerValue],per=[spec[@"per_invocation_bytes"]unsignedIntegerValue],minimum=[spec[@"minimum_bytes"]unsignedIntegerValue],count=volume(c.groups,65536)*volume(c.local,1024);
    if(!align||off%align||!count||count>65536||per>NSUIntegerMax/count||MAX(minimum,per*count)>buffer.length-off){fail(error,@"IR v2 reflected alignment/extent differs");return nil;}
   }
   for(id<MTLBuffer>other in blocked){uint64_t b=other.gpuAddress;if(buffer==other||(a<b+other.length&&b<a+buffer.length)){fail(error,@"IR v2 resource catalogue aliases retained state/input");return nil;}}
   for(NSDictionary*use in catalogueUses){id<MTLBuffer>other=use[@"buffer"];uint64_t b=other.gpuAddress;if(buffer==other||(a<b+other.length&&b<a+buffer.length)){BOOL exactAcrossEntries=buffer==other&&off==[use[@"offset"]unsignedIntegerValue]&&k!=[use[@"entry"]unsignedIntegerValue];if(!exactAcrossEntries){fail(error,@"IR v2 resource catalogue aliases within an entry or overlaps partially");return nil;}}}
   if(![owners containsObject:buffer])[owners addObject:buffer];[catalogueUses addObject:@{@"buffer":buffer,@"offset":@(off),@"entry":@(k)}];a+=off;memcpy((char*)addresses.mutableBytes+k*32+i*8,&a,8);
  }
  for(NSUInteger earlier=0;earlier<k;earlier++)if(!memcmp((const char*)addresses.bytes+earlier*32,(const char*)addresses.bytes+k*32,32)){fail(error,@"IR v2 resource catalogue duplicates an entry");return nil;}
 }
 KPGPUCommandSelection*plan=[self newGPUCommandSelectionFromBuffer:source sourceRange:range destination:destination destinationRange:targetRange input:records inputOffset:offset nonce:0 error:error];if(!plan)return nil;
 plan.commandIRStablePipelineIdentities=stable;
 plan.reusableContext=reusable;plan.reusableGeneration=generation;
 plan.resourceOwners=[owners copy];plan.resourceAddresses=[_device newBufferWithBytes:addresses.bytes length:addresses.length options:MTLResourceStorageModeShared];plan.constantTemplates=[_device newBufferWithLength:range.length*65536 options:MTLResourceStorageModePrivate];plan.generatedGeometry=[_device newBufferWithLength:128+targetRange.length*64 options:MTLResourceStorageModePrivate];plan.commandIRLimits=[_device newBufferWithLength:range.length*48 options:MTLResourceStorageModeShared];plan.commandIRContext=reusable?reusable.buffer:[_device newBufferWithLength:stable?sizeof(KPStableCommandContext):sizeof(KPCommandContext)options:MTLResourceStorageModePrivate];
 if(!plan.resourceAddresses||!plan.constantTemplates||!plan.generatedGeometry||!plan.commandIRLimits||!plan.commandIRContext){fail(error,@"IR v2 owned allocation failed");return nil;}
 NSMutableArray*parameters=[NSMutableArray new],*parameterAddresses=[NSMutableArray new];
 for(NSUInteger i=0;i<range.length;i++){
  KPComputeICBCommand*c=sourceCommands[i];NSDictionary*binding=c.bindings[@(constantIndex)];id<MTLBuffer>b=binding[@"buffer"];uint64_t a=b.gpuAddress+[binding[@"offset"]unsignedIntegerValue];uint32_t row[12]={(uint32_t)c.groups.width,(uint32_t)c.groups.height,(uint32_t)c.groups.depth,0,(uint32_t)c.local.width,(uint32_t)c.local.height,(uint32_t)c.local.depth,(uint32_t)[c.threadgroupLengths[@0]unsignedIntegerValue],(uint32_t)a,(uint32_t)(a>>32),(uint32_t)constantIndex,(uint32_t)n};memcpy((char*)plan.commandIRLimits.contents+i*48,row,48);[parameters addObject:b];[parameterAddresses addObject:@(a)];
 }
 plan.commandIRParameters=[parameters copy];plan.commandIRParameterAddresses=[parameterAddresses copy];
 // A native buffer binding has descriptor identifiers and an offset in addition
 // to its VA. Capture each full32B entry through the unchanged native encoder.
 // Preparation suppresses all user launches, as for original command templates.
 NSMutableArray*bindingRecords=[NSMutableArray new];
 for(NSUInteger candidate=0;candidate<sourceCommands.count;candidate++)for(NSUInteger k=0;k<resources.count;k++){
  KPComputeICBCommand*c=sourceCommands[candidate],*probe=[KPComputeICBCommand new];probe.owner=c.owner;[probe copyStateFrom:c];[probe invalidate];
  NSDictionary*profile=[self profileForPipeline:c.pipeline];NSArray*bindings=resources[k][@"bindings"];
  for(NSUInteger i=0;i<bindings.count;i++){NSUInteger slot=i<constantIndex?i:i+1;if(profile[@"binding_specs"][@(slot)])probe.bindings[@(slot)]=bindings[i];}
  NSString*invalid=residentBindingError(probe,self);if(invalid){fail(error,invalid);return nil;}
  KPRecordedNativeCompute*r=[self materialize:probe];if(!r){fail(error,@"IR v2 native resource descriptor capture failed");return nil;}[bindingRecords addObject:r];
 }
 plan.commandIRBindingRecords=[bindingRecords copy];plan.commandIRNativeBindings=[_device newBufferWithLength:bindingRecords.count*128 options:MTLResourceStorageModePrivate];
 if(!plan.commandIRNativeBindings){fail(error,@"IR v2 native binding table allocation failed");return nil;}
 NSMutableArray*configs=[NSMutableArray new];for(NSUInteger i=0;i<targetRange.length;i++){id<MTLBuffer>c=[_device newBufferWithLength:256 options:MTLResourceStorageModeShared];if(!c){fail(error,@"IR v2 config allocation failed");return nil;}memset(c.contents,0,256);memcpy(c.contents,plan.selectorConfigs[i].contents,16);uint64_t a=plan.targetRecords[i].constants.gpuAddress;uint32_t w[4]={(uint32_t)resources.count,(uint32_t)a,(uint32_t)(a>>32),0};memcpy((char*)c.contents+16,w,16);[configs addObject:c];}plan.selectorConfigs=[configs copy];
 KPStableCommandContext context={};context.base={stable?KP_COMMAND_STABLE_CONTEXT_MAGIC:KP_COMMAND_CONTEXT_MAGIC,stable?KP_COMMAND_STABLE_CONTEXT_VERSION:KP_COMMAND_IR_VERSION2,(uint32_t)targetRange.length,(uint32_t)n,records.gpuAddress+offset,KP_COMMAND_RECORD_BYTES,(uint32_t)range.length};
 if(reusable){context.base.magic=KP_COMMAND_REUSABLE_CONTEXT_MAGIC;context.base.version=(generation<<8)|KP_COMMAND_REUSABLE_CONTEXT_VERSION;}
 NSMutableArray*identities=[NSMutableArray new];
 if(stable)for(NSUInteger i=0;i<sourceCommands.count;i++){
  KPComputeICBCommand*c=sourceCommands[i];uint64_t identity=[self commandIRIdentityForPipeline:c.pipeline error:error];if(!identity)return nil;[identities addObject:@(identity)];
  KPCommandPipelineIdentity&e=context.pipelines[i];e.identity=identity;e.parameters_address=[plan.commandIRParameterAddresses[i]unsignedLongLongValue];
  e.groups[0]=c.groups.width;e.groups[1]=c.groups.height;e.groups[2]=c.groups.depth;e.local[0]=c.local.width;e.local[1]=c.local.height;e.local[2]=c.local.depth;e.shared_bytes=[c.threadgroupLengths[@0]unsignedIntValue];e.constant_index=constantIndex;
 }
 plan.commandIRPipelineIdentities=[identities copy];NSUInteger contextBytes=plan.commandIRContext.length;
 id<MTLBuffer>initial=[_device newBufferWithBytes:&context length:contextBytes options:MTLResourceStorageModeShared];
 id<MTLCommandBuffer>cb=[_queue commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];if(!initial||!b){fail(error,@"IR v2 initializer missing");return nil;}
 for(NSUInteger i=0;i<range.length;i++)[b copyFromBuffer:sourceCommands[i].record.constants sourceOffset:0 toBuffer:plan.constantTemplates destinationOffset:i*65536 size:65536];
 for(NSUInteger i=0;i<bindingRecords.count;i++)[b copyFromBuffer:((KPRecordedNativeCompute*)bindingRecords[i]).constants sourceOffset:0 toBuffer:plan.commandIRNativeBindings destinationOffset:i*128 size:128];
 [b fillBuffer:plan.generatedGeometry range:NSMakeRange(0,plan.generatedGeometry.length)value:0xa5];[b fillBuffer:plan.generatedGeometry range:NSMakeRange(64,targetRange.length*64)value:0];[b copyFromBuffer:initial sourceOffset:0 toBuffer:plan.commandIRContext destinationOffset:0 size:contextBytes];[b endEncoding];if(!complete(cb)){if(reusable)reusable.poisoned=YES;fail(error,@"IR v2 initialization failed");return nil;}
 KPCommandIRArgumentContext*ac=[KPCommandIRArgumentContext new];ac.plan=plan;ac.context=plan.commandIRContext;NSMutableArray*leases=[NSMutableArray arrayWithObjects:plan.input,plan.commandIRContext,nil];[leases addObjectsFromArray:plan.commandIRParameters];[leases addObjectsFromArray:plan.resourceOwners];[leases addObjectsFromArray:blocked];ac.resources=[leases copy];ac.bindingCount=n;ac.constantIndex=constantIndex;ac.ownerThread=NSThread.currentThread;ac.roots=[NSMutableArray new];
 NSMutableArray*ap=[NSMutableArray new],*ab=[NSMutableArray new],*ar=[NSMutableArray new];
 for(KPComputeICBCommand*c in sourceCommands){[ap addObject:c.pipeline];NSDictionary*b=c.bindings[@(constantIndex)];[ab addObject:@{@"buffer":b[@"buffer"],@"offset":@([b[@"offset"]unsignedIntegerValue])}];}
 for(NSDictionary*entry in resources){NSMutableArray*bindings=[NSMutableArray new];for(NSDictionary*b in entry[@"bindings"])[bindings addObject:@{@"buffer":b[@"buffer"],@"offset":@([b[@"offset"]unsignedIntegerValue])}];[ar addObject:[bindings copy]];}
 ac.pipelines=[ap copy];ac.parameters=[ab copy];ac.catalogue=[ar copy];plan.commandIRArgumentContext=ac;plan.commandIRArgumentRoots=ac.roots;d.commandIRArgumentContext=ac;
 plan.commandIRGeneration=YES;plan.commandIRVersion=2;plan.commandIRBufferCount=n;plan.commandIRConstantIndex=constantIndex;plan.gridPrefix=YES;plan.bindingGeneration=YES;[_eventRows addObject:@{@"operation":@"prepare_GPU_command_IR_v2",@"rows":@(targetRange.length),@"candidate_count":@(range.length),@"binding_count":@(n),@"constant_index":@(constantIndex),@"record_CPU_read":@NO,@"uniform_multidimensional":@YES,@"reflected_buffer_extents_validated":@YES,@"exact_cross_entry_sharing":@YES,@"native_binding_entry_bytes":@32,@"native_binding_template_count":@(bindingRecords.count),@"native_binding_user_dispatches":@0,@"opaque_native_descriptors_preserved":@YES}];return plan;
}
