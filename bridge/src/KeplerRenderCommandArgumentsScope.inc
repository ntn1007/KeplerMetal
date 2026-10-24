// SPDX-License-Identifier: MIT
// Included after render-catalogue validation inside KPCPUICBScope.
- (id<MTLFunction>)newRenderCommandFunctionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected functionName:(NSString*)name rootBufferIndex:(NSUInteger)index error:(NSError**)error{
 @synchronized(_factoryLock){
  if(error)*error=nil;
  if(_restored||!_renderEngine||!_indirectRenderStatePipeline||index||![data isKindOfClass:NSData.class]||!data.length||data.length>16*1024*1024||!digestString(expected)||!name.length){fail(error,@"Active render catalogue scope and a pinned lowered library are required");return nil;}
  NSData*snapshot=[NSData dataWithBytes:data.bytes length:data.length];expected=[expected copy];name=[name copy];
  if(![hash(snapshot)isEqual:expected]){fail(error,@"Render producer library fingerprint differs");return nil;}
  id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);id<MTLFunction>function=[library newFunctionWithName:name];
  if(!function||function.device!=_device||function.functionType!=MTLFunctionTypeKernel||function.functionConstantsDictionary.count){fail(error,@"Render producer function identity differs");return nil;}
  KPIRFunctionLink*existing=objc_getAssociatedObject(function,&IRFunctionKey);
  if(existing){if(existing.scope==self&&existing.renderRecordRoot&&[existing.librarySHA isEqual:expected])return function;fail(error,@"Function already has another root ABI");return nil;}
  MTLArgument*argument=nil;id<MTLArgumentEncoder>native=nil;
  nativeFunctionArgumentDepth++;@try{native=[function newArgumentEncoderWithBufferIndex:0 reflection:&argument];}@catch(NSException*x){fail(error,x.reason);}@finally{nativeFunctionArgumentDepth--;}
  NSDictionary*schema=renderRecordFunctionSchema(argument,native,0);if(!schema){fail(error,@"Native lowered render root reflection differs");return nil;}
  Class original=object_getClass(function),dynamic=nil;
  {std::lock_guard<std::mutex>lock(installMutex);
   if(!installRenderOverride(object_getClass(_device),_originalDeviceClass,@selector(newArgumentEncoderWithArguments:),(IMP)createIRArgumentEncoder)){fail(error,@"Cannot install the scoped root factory");return nil;}
   dynamic=scopedClass(functionClasses,original,@"KPIRFunction_",@selector(newArgumentEncoderWithBufferIndex:),(IMP)functionIRArguments,error);
   if(!dynamic||!installRenderOverride(dynamic,original,@selector(newArgumentEncoderWithBufferIndex:reflection:),(IMP)functionIRArgumentsWithReflection)){fail(error,@"Cannot install function-local render root getters");return nil;}
  }
  KPIRFunctionLink*link=[KPIRFunctionLink new];link.scope=self;link.originalClass=original;link.bufferIndex=0;link.renderRecordRoot=YES;link.librarySHA=expected;link.schema=schema;
  objc_setAssociatedObject(function,&IRFunctionKey,link,OBJC_ASSOCIATION_RETAIN_NONATOMIC);object_setClass(function,dynamic);
  KPAdaptedFunction*record=[KPAdaptedFunction new];record.function=function;record.originalClass=original;if(!_adaptedFunctions)_adaptedFunctions=[NSMutableArray new];[_adaptedFunctions addObject:record];
  if(!_functionLibraries)_functionLibraries=[NSMutableArray new];[_functionLibraries addObject:@{@"library":library,@"bytes":snapshot}];_renderRecordArgumentsEnabled=YES;
  [_eventRows addObject:@{@"operation":@"register_render_record_function",@"function":name,@"library_SHA256":expected,@"schema":schema,@"native_pipeline_factories_preserved":@YES,@"native_reflection_preserved":@YES,@"Apple_native_ICB_identity":@NO}];return function;
 }
}
- (BOOL)validateRenderCommandArgumentContext:(KPRenderCommandArgumentContext*)c error:(NSError**)error{
 if(_restored||!_renderRecordArgumentsEnabled||object_getClass(c)!=KPRenderCommandArgumentContext.class||c.scope!=self||c.ownerThread!=NSThread.currentThread||c.prepared||c.completed||c.failed||!c.target||c.target.renderArgumentContext!=c||c.commandBuffer.commandQueue!=_queue||c.commandBuffer.status!=MTLCommandBufferStatusNotEnqueued||!c.commandBuffer.retainedReferences)
  return fail(error,@"Render argument context is stale, pending, foreign or off-thread");
 NSArray*sources=liveRenderCatalogueSources(c.catalogue,self,error);if(!sources||sources.firstObject!=c.target||c.capacity!=c.target.size)return fail(error,@"Render argument catalogue/target changed");
 return YES;
}
- (KPRenderCommandArgumentContext*)newRenderCommandArgumentContextWithCommands:(id<MTLIndirectCommandBuffer>)commands stateCatalogue:(KPRenderStateCatalogue*)catalogue commandRecords:(id<MTLBuffer>)records commandRecordsOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error{
 @synchronized(_factoryLock){
  NSArray*sources=liveRenderCatalogueSources(catalogue,self,error);
  if(!_renderRecordArgumentsEnabled||!sources||sources.firstObject!=commands||cb.commandQueue!=_queue||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences||records.device!=_device||records.storageMode!=MTLStorageModePrivate||offset%16||offset>records.length||catalogue.logicalCommandCount>16||catalogue.logicalCommandCount*64>records.length-offset||!records.gpuAddress||records.gpuAddress>>40||records.length>((uint64_t(1)<<40)-records.gpuAddress)){
   fail(error,@"Render argument records, catalogue, queue or bounds differ");return nil;
  }
  KPRenderICB*target=(KPRenderICB*)commands;KPRenderCommandArgumentContext*old=target.renderArgumentContext;
  if(old&&!old.completed&&old.commandBuffer){fail(error,@"Render ICB already has a recording or pending context");return nil;}
  KPRenderCommandArgumentContext*c=[[KPRenderCommandArgumentContext alloc]initOwned];c.scope=self;c.target=target;c.catalogue=catalogue;c.commandBuffer=cb;c.ownerThread=NSThread.currentThread;c.capacity=target.size;c.commandRecords=records;c.commandRecordsOffset=offset;c.contextOffset=64;c.roots=[NSMutableArray new];
  struct Header{uint32_t magic,version,capacity,bytes;uint64_t records,reserved;};static_assert(sizeof(Header)==32,"Render root context ABI");
  NSMutableData*data=[NSMutableData dataWithLength:160];memset(data.mutableBytes,0xa5,data.length);Header header={0x4b505243,1,(uint32_t)c.capacity,64,records.gpuAddress+offset,0};memcpy((char*)data.mutableBytes+64,&header,32);
  id<MTLBuffer>stage=[_device newBufferWithBytes:data.bytes length:data.length options:MTLResourceStorageModeShared];c.contextBuffer=[_device newBufferWithLength:160 options:MTLResourceStorageModePrivate];
  if(!stage||!c.contextBuffer||!c.contextBuffer.gpuAddress||c.contextBuffer.gpuAddress>>40||c.contextBuffer.length>((uint64_t(1)<<40)-c.contextBuffer.gpuAddress)){fail(error,@"Render context allocation failed");return nil;}
  id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];if(!blit){fail(error,@"Render context upload failed; discard command buffer");return nil;}[blit copyFromBuffer:stage sourceOffset:0 toBuffer:c.contextBuffer destinationOffset:0 size:160];[blit endEncoding];
  [cb addCompletedHandler:^(id<MTLCommandBuffer>done){c.failed=done.status!=MTLCommandBufferStatusCompleted;c.completed=YES;(void)stage.length;}];
  target.renderArgumentContext=c;if(!_renderArgumentContexts)_renderArgumentContexts=[NSHashTable weakObjectsHashTable];[_renderArgumentContexts addObject:c];
  [_eventRows addObject:@{@"operation":@"create_render_record_argument_context",@"capacity":@(c.capacity),@"context_bytes":@32,@"record_bytes":@64,@"record_offset":@(offset),@"same_recording_CB":@YES,@"client_GPU_address_required":@NO}];return c;
 }
}
- (BOOL)prepareRenderCommandArgumentContext:(KPRenderCommandArgumentContext*)c argumentBuffer:(id<MTLBuffer>)root offset:(NSUInteger)offset computeEncoder:(id<MTLComputeCommandEncoder>)encoder commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error{
 @synchronized(_factoryLock){
  if(![self validateRenderCommandArgumentContext:c error:error]||c.commandBuffer!=cb||encoder.device!=_device)return fail(error,@"Render root producer/encoder differs");
  Ivar slot=class_getInstanceVariable(object_getClass(encoder),"_commandBuffer");if(!slot||ivar_getOffset(slot)!=32||object_getIvar(encoder,slot)!=cb)return fail(error,@"Render root compute encoder profile differs");
  NSMutableDictionary*found=nil;
  for(NSMutableDictionary*r in c.roots)if(r[@"buffer"]==root&&[r[@"offset"]unsignedIntegerValue]==offset){found=r;break;}
  NSData*expected=found[@"expected"];
  if(!found||![found[@"complete"]boolValue]||expected.length!=8||root.storageMode!=MTLStorageModeShared||!root.contents||offset>root.length||8>root.length-offset||memcmp((char*)root.contents+offset,expected.bytes,8))return fail(error,@"Render root was not exported intact by its argument encoder");
  [encoder setBuffer:root offset:offset atIndex:0];[encoder useResource:c.contextBuffer usage:MTLResourceUsageRead];[encoder useResource:c.commandRecords usage:MTLResourceUsageRead|MTLResourceUsageWrite];c.prepared=YES;
  [_eventRows addObject:@{@"operation":@"prepare_render_record_arguments",@"root_bytes":@8,@"root_offset":@(offset),@"indirect_resources_declared":@YES,@"roots_retained_until_completion":@YES,@"native_pipeline_unchanged":@YES}];return YES;
 }
}
