// Included within KPGPUCommandSelection's implementation.
- (NSArray<id<MTLBuffer>>*)commandIRProducerResources {
 if(!_commandIRGeneration)return @[];
 NSMutableArray*resources=[NSMutableArray arrayWithObjects:_input,_commandIRContext,nil];
 [resources addObjectsFromArray:_commandIRParameters];[resources addObjectsFromArray:_resourceOwners];
 for(NSDictionary*r in _commandIRArgumentRoots){id b=r[@"buffer"];if(b&&![resources containsObject:b])[resources addObject:b];}return [resources copy];
}
- (BOOL)validateCommandIRArgumentBindings:(NSError**)error {
 if(!_commandIRGeneration||_commandIRVersion!=2||_selectionBuffer||![self validateOwners:error])return fail(error,@"Command IR argument plan is inactive");
 for(NSDictionary*r in _commandIRArgumentRoots){id<MTLBuffer>b=r[@"buffer"];NSUInteger off=[r[@"offset"]unsignedIntegerValue];NSData*expected=r[@"expected"];
  if(![r[@"complete"]boolValue]||!expected||b.storageMode!=MTLStorageModeShared||!b.contents||off>b.length||expected.length>b.length-off||memcmp((const char*)b.contents+off,expected.bytes,expected.length))return fail(error,r[@"reason"]?:@"Command IR arguments are incomplete or caller-modified");
 }
 return YES;
}
- (id<MTLBuffer>)newCommandIRArgumentsForCandidateIndex:(NSUInteger)candidate resourceIndex:(NSUInteger)resource error:(NSError**)error {
 if(_commandIRVersion==2){
  if(!_commandIRGeneration||_selectionBuffer||candidate>=_candidateCount||resource>=_resourceAddresses.length/32||![self validateOwners:error]){fail(error,@"Command IR v2 root candidate/resource/state differs");return nil;}
  uint64_t a[4]={};memcpy(a,(const char*)_resourceAddresses.contents+resource*32,32);uint64_t root[6]={_commandIRContext.gpuAddress,(uint64_t(KP_COMMAND_PIPELINE_MAGIC)<<32)|candidate,0,0,0,0};NSUInteger mutableIndex=0;
  if(_commandIRStablePipelineIdentities)root[1]=[_commandIRPipelineIdentities[candidate]unsignedLongLongValue];
  if(_reusableContext)root[0]|=uint64_t(_reusableGeneration)<<KP_COMMAND_CONTEXT_GENERATION_SHIFT;
  for(NSUInteger slot=0;slot<_commandIRBufferCount;slot++)root[2+slot]=slot==_commandIRConstantIndex?[_commandIRParameterAddresses[candidate]unsignedLongLongValue]:a[mutableIndex++];
  id<MTLBuffer>argument=[_scope.device newBufferWithBytes:root length:sizeof root options:MTLResourceStorageModeShared];if(!argument)fail(error,@"Command IR v2 root allocation failed");return argument;
 }
 if(!_commandIRGeneration||_selectionBuffer||candidate>=_candidateCount||resource>=_resourceAddresses.length/16||![self validateOwners:error]){fail(error,@"Command IR root candidate/resource/state differs");return nil;}
 uint64_t addresses[2]={};memcpy(addresses,(const char*)_resourceAddresses.contents+resource*16,16);
 uint64_t root[5]={_commandIRContext.gpuAddress,(uint64_t(KP_COMMAND_PIPELINE_MAGIC)<<32)|candidate,addresses[0],addresses[1],[_commandIRParameterAddresses[candidate]unsignedLongLongValue]};
 id<MTLBuffer>argument=[_scope.device newBufferWithBytes:root length:sizeof root options:MTLResourceStorageModeShared];
 if(!argument)fail(error,@"Command IR root allocation failed");return argument;
}
- (BOOL)encodeCommandIRInCommandBuffer:(id<MTLCommandBuffer>)cb afterProducer:(id<MTLCommandBuffer>)producer error:(NSError**)error {
 if(!_commandIRGeneration||_selectionBuffer)return fail(error,@"Command IR plan is unavailable/already materialized");
 if(_commandIRArgumentRoots.count&&![self validateCommandIRArgumentBindings:error])return NO;
 if(producer&&!residentPredecessorOrder(producer,cb))return fail(error,@"Command IR producer must precede consumer on the same retained queue");
 if(_reusableContext){if(producer&&_producerBuffer!=producer)return fail(error,@"Reusable producer must reserve its context before encoding");if(![_reusableContext track:cb generation:_reusableGeneration error:error])return NO;}
 _producerBuffer=producer;return [self encodeSelectionInCommandBuffer:cb error:error];
}
- (BOOL)reserveCommandIRProducerInCommandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error {
 if(!_reusableContext||_selectionBuffer||(_producerBuffer&&_producerBuffer!=cb)||![self acceptBuffer:cb error:error]||![self validateCommandIRArgumentBindings:error])return fail(error,@"Reusable producer reservation is unavailable");
 if(![_reusableContext track:cb generation:_reusableGeneration error:error])return NO;
 _producerBuffer=cb;_reusableContext.resources=self.commandIRProducerResources;
 [_eventRows addObject:@{@"operation":@"reserve_reusable_IR_producer",@"generation":@(_reusableGeneration),@"buffer_status":@(cb.status)}];return YES;
}
