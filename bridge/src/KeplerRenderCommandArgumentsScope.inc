// SPDX-License-Identifier: MIT
// Included after render-catalogue validation inside KPCPUICBScope.
- (id<MTLFunction>)newRenderCommandFunctionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected functionName:(NSString*)name rootBufferIndex:(NSUInteger)index error:(NSError**)error{
 return[self newRenderCommandFunctionWithLibraryData:data expectedSHA256:expected functionName:name rootBufferIndex:index pipelineRoot:NO error:error];
}
- (id<MTLFunction>)newPipelineRenderCommandFunctionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected functionName:(NSString*)name rootBufferIndex:(NSUInteger)index error:(NSError**)error{
 return[self newRenderCommandFunctionWithLibraryData:data expectedSHA256:expected functionName:name rootBufferIndex:index pipelineRoot:YES error:error];
}
- (id<MTLFunction>)newRenderCommandFunctionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected functionName:(NSString*)name rootBufferIndex:(NSUInteger)index pipelineRoot:(BOOL)pipeline error:(NSError**)error{
 @synchronized(_factoryLock){
  if(error)*error=nil;
  if(_restored||!_renderEngine||!_indirectRenderStatePipeline||index||![data isKindOfClass:NSData.class]||!data.length||data.length>16*1024*1024||!digestString(expected)||!name.length){fail(error,@"Active render catalogue scope and a pinned lowered library are required");return nil;}
  NSData*snapshot=[NSData dataWithBytes:data.bytes length:data.length];expected=[expected copy];name=[name copy];
  if(![hash(snapshot)isEqual:expected]){fail(error,@"Render producer library fingerprint differs");return nil;}
  id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);id<MTLFunction>function=[library newFunctionWithName:name];
  if(!function||function.device!=_device||function.functionType!=MTLFunctionTypeKernel||function.functionConstantsDictionary.count){fail(error,@"Render producer function identity differs");return nil;}
  KPIRFunctionLink*existing=objc_getAssociatedObject(function,&IRFunctionKey);
  if(existing){if(existing.scope==self&&existing.renderRecordRoot&&existing.pipelineRenderRoot==pipeline&&[existing.librarySHA isEqual:expected])return function;fail(error,@"Function already has another root ABI");return nil;}
  MTLArgument*argument=nil;id<MTLArgumentEncoder>native=nil;
  nativeFunctionArgumentDepth++;@try{native=[function newArgumentEncoderWithBufferIndex:0 reflection:&argument];}@catch(NSException*x){fail(error,x.reason);}@finally{nativeFunctionArgumentDepth--;}
  NSDictionary*schema=pipeline?pipelineRenderFunctionSchema(argument,native,0):renderRecordFunctionSchema(argument,native,0);if(!schema){fail(error,@"Native lowered render root reflection differs");return nil;}
  Class original=object_getClass(function),dynamic=nil;
  {std::lock_guard<std::mutex>lock(installMutex);
   if(!installRenderOverride(object_getClass(_device),_originalDeviceClass,@selector(newArgumentEncoderWithArguments:),(IMP)createIRArgumentEncoder)){fail(error,@"Cannot install the scoped root factory");return nil;}
   dynamic=scopedClass(functionClasses,original,@"KPIRFunction_",@selector(newArgumentEncoderWithBufferIndex:),(IMP)functionIRArguments,error);
   if(!dynamic||!installRenderOverride(dynamic,original,@selector(newArgumentEncoderWithBufferIndex:reflection:),(IMP)functionIRArgumentsWithReflection)){fail(error,@"Cannot install function-local render root getters");return nil;}
  }
  KPIRFunctionLink*link=[KPIRFunctionLink new];link.scope=self;link.originalClass=original;link.bufferIndex=0;link.renderRecordRoot=YES;link.pipelineRenderRoot=pipeline;link.librarySHA=expected;link.schema=schema;
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
 return[self newRenderCommandArgumentContextWithCommands:commands stateCatalogue:catalogue commandRecords:records commandRecordsOffset:offset commandBuffer:cb indexedBindings:NO vertexBindings:NO pipelineBindings:NO error:error];
}
- (KPRenderCommandArgumentContext*)newPipelineRenderCommandArgumentContextWithCommands:(id<MTLIndirectCommandBuffer>)commands stateCatalogue:(KPRenderStateCatalogue*)catalogue commandRecords:(id<MTLBuffer>)records commandRecordsOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error{
 return[self newRenderCommandArgumentContextWithCommands:commands stateCatalogue:catalogue commandRecords:records commandRecordsOffset:offset commandBuffer:cb indexedBindings:NO vertexBindings:NO pipelineBindings:YES error:error];
}
- (KPRenderCommandArgumentContext*)newIndexedRenderCommandArgumentContextWithCommands:(id<MTLIndirectCommandBuffer>)commands stateCatalogue:(KPRenderStateCatalogue*)catalogue commandRecords:(id<MTLBuffer>)records commandRecordsOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error{
 return[self newRenderCommandArgumentContextWithCommands:commands stateCatalogue:catalogue commandRecords:records commandRecordsOffset:offset commandBuffer:cb indexedBindings:YES vertexBindings:NO pipelineBindings:NO error:error];
}
- (KPRenderCommandArgumentContext*)newVertexRenderCommandArgumentContextWithCommands:(id<MTLIndirectCommandBuffer>)commands stateCatalogue:(KPRenderStateCatalogue*)catalogue commandRecords:(id<MTLBuffer>)records commandRecordsOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error{
 return[self newRenderCommandArgumentContextWithCommands:commands stateCatalogue:catalogue commandRecords:records commandRecordsOffset:offset commandBuffer:cb indexedBindings:NO vertexBindings:YES pipelineBindings:NO error:error];
}
- (KPRenderCommandArgumentContext*)newIndexedVertexRenderCommandArgumentContextWithCommands:(id<MTLIndirectCommandBuffer>)commands stateCatalogue:(KPRenderStateCatalogue*)catalogue commandRecords:(id<MTLBuffer>)records commandRecordsOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error{
 return[self newRenderCommandArgumentContextWithCommands:commands stateCatalogue:catalogue commandRecords:records commandRecordsOffset:offset commandBuffer:cb indexedBindings:YES vertexBindings:YES pipelineBindings:NO error:error];
}
- (KPRenderCommandArgumentContext*)newIndexedVertexPipelineRenderCommandArgumentContextWithCommands:(id<MTLIndirectCommandBuffer>)commands stateCatalogue:(KPRenderStateCatalogue*)catalogue commandRecords:(id<MTLBuffer>)records commandRecordsOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error{
 return[self newRenderCommandArgumentContextWithCommands:commands stateCatalogue:catalogue commandRecords:records commandRecordsOffset:offset commandBuffer:cb indexedBindings:YES vertexBindings:YES pipelineBindings:YES error:error];
}
- (KPRenderCommandArgumentContext*)newRenderCommandArgumentContextWithCommands:(id<MTLIndirectCommandBuffer>)commands stateCatalogue:(KPRenderStateCatalogue*)catalogue commandRecords:(id<MTLBuffer>)records commandRecordsOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb indexedBindings:(BOOL)indexed vertexBindings:(BOOL)vertex pipelineBindings:(BOOL)pipeline error:(NSError**)error{
 @synchronized(_factoryLock){
  if(error)*error=nil;
  NSArray*sources=liveRenderCatalogueSources(catalogue,self,error);
  if((pipeline&&(indexed!=vertex))||!_renderRecordArgumentsEnabled||!sources||sources.firstObject!=commands||cb.commandQueue!=_queue||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences||records.device!=_device||records.storageMode!=MTLStorageModePrivate||offset%16||offset>records.length||catalogue.logicalCommandCount>16||catalogue.logicalCommandCount*64>records.length-offset||!records.gpuAddress||records.gpuAddress>>40||records.length>((uint64_t(1)<<40)-records.gpuAddress)){
   fail(error,@"Render argument records, catalogue, queue or bounds differ");return nil;
  }
  KPRenderICB*target=(KPRenderICB*)commands;KPRenderCommandArgumentContext*old=target.renderArgumentContext;
  if(old&&!old.completed&&old.commandBuffer){fail(error,@"Render ICB already has a recording or pending context");return nil;}
  NSMutableData *indexData=[NSMutableData new];NSMutableArray *indexOwners=[NSMutableArray new];
  if(indexed)for(NSUInteger slot=0;slot<catalogue.logicalCommandCount;slot++)for(NSUInteger state=0;state<sources.count;state++){
   KPRenderICBCommand *command=((KPRenderICB*)sources[state]).commands[slot];
   if(!command.hasDraw||!command.kind)continue;
   NSUInteger bytes=command.kind==1?2:command.kind==2?4:0;
   id<MTLBuffer>buffer=command.indices;uint64_t address=buffer.gpuAddress;
   if(!bytes||buffer.device!=_device||command.vertexCount>UINT32_MAX||command.offset>buffer.length||command.offset%bytes||command.vertexCount>(buffer.length-command.offset)/bytes||!address||address>>40||buffer.length>((uint64_t(1)<<40)-address)){
    fail(error,@"Indexed render binding identity, alignment or bounds differ");return nil;
   }
   uint64_t start=address+command.offset,length=command.vertexCount*bytes,recordStart=records.gpuAddress+offset,recordEnd=recordStart+catalogue.logicalCommandCount*64;
   if(length&&start<recordEnd&&recordStart<start+length){fail(error,@"Indexed render bindings overlap producer records");return nil;}
   KPRenderIndexBinding row={[catalogue.stateIdentifiers[state]unsignedLongLongValue],start,length,(uint32_t)slot,(uint32_t)command.kind,(uint32_t)command.vertexCount,0,0};
   [indexData appendBytes:&row length:sizeof(row)];[indexOwners addObject:buffer];
  }
  NSUInteger indexCount=indexData.length/sizeof(KPRenderIndexBinding);
  if(indexed&&(!indexCount||indexCount>KP_RENDER_INDEX_BINDING_LIMIT)){fail(error,@"An indexed render catalogue with at most16 bindings is required");return nil;}
  NSMutableData *vertexData=[NSMutableData new];NSMutableArray *vertexOwners=[NSMutableArray new];
  if(vertex&&!kpCreateVertexTransitionRows(sources,catalogue,_device,records,offset,vertexData,vertexOwners)){
   fail(error,@"Vertex transition snapshots, bindings, aliases or row bounds differ");return nil;
  }
  NSUInteger vertexCount=vertexData.length/sizeof(KPVertexTransition::Row);
  if(vertex&&(!vertexCount||vertexCount>KP_RENDER_VERTEX_BINDING_LIMIT)){fail(error,@"Vertex transition count outside supported bound");return nil;}
  NSMutableData*pipelineData=[NSMutableData new];NSMutableArray*pipelineOwners=[NSMutableArray new],*pipelineResources=[NSMutableArray new];NSMutableDictionary*pipelineTokens=[NSMutableDictionary new];
  if(pipeline&&!kpCreatePipelineTransitionRows(sources,catalogue,_device,records,offset,pipelineData,pipelineResources,pipelineOwners,pipelineTokens)){
   fail(error,@"Pipeline transitions, object ownership or row bounds differ");return nil;
  }
  NSUInteger pipelineCount=pipelineData.length/sizeof(KPPipelineTransition::Row);
  if(pipeline&&(!pipelineCount||pipelineCount>KPVertexTransition::MaxRows)){fail(error,@"Pipeline transition count outside supported bound");return nil;}
  [vertexOwners addObjectsFromArray:pipelineResources];
  KPRenderCommandArgumentContext*c=[[KPRenderCommandArgumentContext alloc]initOwned];c.scope=self;c.target=target;c.catalogue=catalogue;c.commandBuffer=cb;c.ownerThread=NSThread.currentThread;c.capacity=target.size;c.commandRecords=records;c.commandRecordsOffset=offset;c.contextOffset=64;c.roots=[NSMutableArray new];
  c.indexBindingCount=indexCount;c.indexBindingTableOffset=indexed?128:0;c.indexOwners=indexOwners;
  NSUInteger vertexExtensionOffset=indexed?128+indexData.length:96;
  c.vertexTransitionCount=vertexCount;c.vertexTransitionTableOffset=vertex?vertexExtensionOffset+32:0;c.vertexOwners=vertexOwners;
  NSUInteger pipelineExtensionOffset=vertex?vertexExtensionOffset+32+vertexData.length:96;
  c.pipelineTransitionCount=pipelineCount;c.pipelineTransitionTableOffset=pipeline?pipelineExtensionOffset+32:0;c.pipelineOwners=pipelineOwners;c.pipelineTokenByObject=pipelineTokens;
  struct Header{uint32_t magic,version,capacity,bytes;uint64_t records,reserved;};static_assert(sizeof(Header)==32,"Render root context ABI");
  NSUInteger size=160+(indexed?32+indexData.length:0)+(vertex?32+vertexData.length:0)+(pipeline?32+pipelineData.length:0);
  c.contextBuffer=[_device newBufferWithLength:size options:MTLResourceStorageModePrivate];
  if(!c.contextBuffer||!c.contextBuffer.gpuAddress||c.contextBuffer.gpuAddress>>40||size>((uint64_t(1)<<40)-c.contextBuffer.gpuAddress)){fail(error,@"Render context allocation failed");return nil;}
  NSMutableData*data=[NSMutableData dataWithLength:size];memset(data.mutableBytes,0xa5,size);Header header={0x4b505243,1,(uint32_t)c.capacity,64,records.gpuAddress+offset,0};memcpy((char*)data.mutableBytes+64,&header,32);
  if(indexed){KPRenderIndexExtension extension={KP_RENDER_INDEX_EXTENSION_MAGIC,KP_RENDER_INDEX_EXTENSION_VERSION,(uint32_t)indexCount,KP_RENDER_INDEX_BINDING_BYTES,c.contextBuffer.gpuAddress+128,0};memcpy((char*)data.mutableBytes+96,&extension,sizeof(extension));memcpy((char*)data.mutableBytes+128,indexData.bytes,indexData.length);}
  if(vertex){KPRenderVertexExtension extension={KP_RENDER_VERTEX_EXTENSION_MAGIC,KP_RENDER_VERTEX_EXTENSION_VERSION,(uint32_t)vertexCount,KP_RENDER_VERTEX_BINDING_BYTES,c.contextBuffer.gpuAddress+c.vertexTransitionTableOffset,0};memcpy((char*)data.mutableBytes+vertexExtensionOffset,&extension,sizeof(extension));memcpy((char*)data.mutableBytes+c.vertexTransitionTableOffset,vertexData.bytes,vertexData.length);}
  if(pipeline){KPRenderVertexExtension extension={0x4b505050,1,(uint32_t)pipelineCount,(uint32_t)sizeof(KPPipelineTransition::Row),c.contextBuffer.gpuAddress+c.pipelineTransitionTableOffset,0};memcpy((char*)data.mutableBytes+pipelineExtensionOffset,&extension,sizeof(extension));memcpy((char*)data.mutableBytes+c.pipelineTransitionTableOffset,pipelineData.bytes,pipelineData.length);}
  id<MTLBuffer>stage=[_device newBufferWithBytes:data.bytes length:size options:MTLResourceStorageModeShared];if(!stage){fail(error,@"Render context staging allocation failed");return nil;}
  id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];if(!blit){fail(error,@"Render context upload failed; discard command buffer");return nil;}[blit copyFromBuffer:stage sourceOffset:0 toBuffer:c.contextBuffer destinationOffset:0 size:size];[blit endEncoding];
  [cb addCompletedHandler:^(id<MTLCommandBuffer>done){c.failed=done.status!=MTLCommandBufferStatusCompleted;c.completed=YES;(void)stage.length;}];
  target.renderArgumentContext=c;if(!_renderArgumentContexts)_renderArgumentContexts=[NSHashTable weakObjectsHashTable];[_renderArgumentContexts addObject:c];
  [_eventRows addObject:@{@"operation":@"create_render_record_argument_context",@"capacity":@(c.capacity),@"context_bytes":@32,@"record_bytes":@64,@"record_offset":@(offset),@"same_recording_CB":@YES,@"client_GPU_address_required":@NO,@"index_bindings":@(indexCount),@"index_buffers_retained":@(indexed),@"index_table_inline":@(indexed),@"vertex_transitions":@(vertexCount),@"vertex_buffers_retained":@(vertex||pipeline),@"pipeline_transitions":@(pipelineCount),@"pipeline_objects_retained":@(pipeline)}];return c;
 }
}
- (BOOL)prepareRenderCommandArgumentContext:(KPRenderCommandArgumentContext*)c argumentBuffer:(id<MTLBuffer>)root offset:(NSUInteger)offset computeEncoder:(id<MTLComputeCommandEncoder>)encoder commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error{
 @synchronized(_factoryLock){
  if(![self validateRenderCommandArgumentContext:c error:error]||c.commandBuffer!=cb||encoder.device!=_device)return fail(error,@"Render root producer/encoder differs");
  Ivar slot=class_getInstanceVariable(object_getClass(encoder),"_commandBuffer");if(!slot||ivar_getOffset(slot)!=32||object_getIvar(encoder,slot)!=cb)return fail(error,@"Render root compute encoder profile differs");
  NSMutableDictionary*found=nil;
  for(NSMutableDictionary*r in c.roots)if(r[@"buffer"]==root&&[r[@"offset"]unsignedIntegerValue]==offset){found=r;break;}
  NSData*expected=found[@"expected"];
  if(!found||![found[@"complete"]boolValue]||(expected.length!=(c.pipelineTransitionCount?16:8))||root.storageMode!=MTLStorageModeShared||!root.contents||offset>root.length||expected.length>root.length-offset||memcmp((char*)root.contents+offset,expected.bytes,expected.length))return fail(error,@"Render root was not exported intact by its argument encoder");
  [encoder setBuffer:root offset:offset atIndex:0];[encoder useResource:c.contextBuffer usage:MTLResourceUsageRead];[encoder useResource:c.commandRecords usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(id<MTLBuffer>buffer in c.indexOwners)[encoder useResource:buffer usage:MTLResourceUsageRead];for(id<MTLBuffer>buffer in c.vertexOwners)[encoder useResource:buffer usage:MTLResourceUsageRead];c.prepared=YES;
  [_eventRows addObject:@{@"operation":@"prepare_render_record_arguments",@"root_bytes":@(expected.length),@"root_offset":@(offset),@"indirect_resources_declared":@YES,@"roots_retained_until_completion":@YES,@"native_pipeline_unchanged":@YES}];return YES;
 }
}
