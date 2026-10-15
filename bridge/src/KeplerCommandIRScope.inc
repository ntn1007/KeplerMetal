// Included within KPCPUICBScope's implementation; no system class changes.
- (BOOL)enableGPUCommandIRWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
 NSString*pin=@"cb9ef0e3985be6155a9c7fde32642fe675c13282fb731c5b2e3669358396d75c";
 NSData*snapshot=data?[NSData dataWithBytes:data.bytes length:data.length]:nil;
 if(_restored||!_GPUBindingSelector||![expected isEqual:pin]||!snapshot||![hash(snapshot)isEqual:pin])return fail(error,@"Command IR materializer identity/binding scope differs");
 if(_GPUCommandIRLibrary)return YES;
 id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);if(!library)return NO;
 id<MTLComputePipelineState>selector=[_device newComputePipelineStateWithFunction:[library newFunctionWithName:@"materialize_compute_command_ir"]error:error];
 if(!selector||selector.threadExecutionWidth!=32||selector.maxTotalThreadsPerThreadgroup<64)return fail(error,@"Command IR materializer pipeline limits differ");
 _GPUCommandIRLibrary=library;_GPUCommandIRSelector=selector;
 [_eventRows addObject:@{@"operation":@"enable_GPU_command_IR",@"library_SHA256":pin,@"arbitrary_QMD_fields_accepted":@NO}];return YES;
}
- (KPGPUCommandSelection*)newGPUCommandIRFromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources records:(id<MTLBuffer>)records recordOffset:(NSUInteger)offset error:(NSError**)error {
 if(!_GPUCommandIRSelector){fail(error,@"Command IR module is not enabled");return nil;}
 // The IR consumer has its own profile validation; the old geometry selector
 // remains restricted to its previously qualified shared kernels.
 NSArray*combined=@[@"shared_mix_s128",@"shared_mix_s1024",@"shared_mix_s4096"];
 NSArray*registered=@[@"manifest_mix",@"manifest_dynamic"];
 for(unsigned pass=0;pass<2;pass++){
  if(![source isKindOfClass:KPComputeICB.class]||![destination isKindOfClass:KPComputeICB.class]){fail(error,@"IR command type differs");return nil;}
  KPComputeICB*buffer=pass?(KPComputeICB*)destination:(KPComputeICB*)source;NSRange selected=pass?targetRange:range;
  if(buffer.scope!=self||!selected.length||selected.length>8||selected.location>buffer.size||selected.length>buffer.size-selected.location){fail(error,@"IR command scope/range differs");return nil;}
  for(NSUInteger i=selected.location;i<NSMaxRange(selected);i++){
   KPComputeICBCommand*c=buffer.commands[i];NSDictionary*p=[self profileForPipeline:c.pipeline];
   BOOL accepted=([p[@"library_SHA256"]isEqual:@"b66637d429769478b5be034572e258f16078760ab511f016aec5a57fc76fdebd"]&&[combined containsObject:p[@"function"]])||([p[@"library_SHA256"]isEqual:@"ed7854542c2a45533f0114fd7e1100f31f52728433f83667b5d9cd54568cea94"]&&[registered containsObject:p[@"function"]]);
   if(!accepted||![p[@"binding_layout_v2"]boolValue]||[p[@"constant_buffer_index"]unsignedIntegerValue]!=2||[p[@"binding_specs"]count]!=3||!p[@"binding_specs"][@0]||!p[@"binding_specs"][@1]||!p[@"binding_specs"][@2]||!c.hasDispatch||!c.groups.width||c.groups.width>7||c.groups.height!=1||c.groups.depth!=1||c.local.height!=1||c.local.depth!=1){fail(error,@"IR consumer profile/binding/uniform1D contract differs");return nil;}
  }
 }
 KPGPUCommandSelection*plan=[self newGPUCommandBindingPlanFromBuffer:source sourceRange:range destination:destination destinationRange:targetRange resources:resources input:records inputOffset:offset nonce:0 IR:YES error:error];if(!plan)return nil;
 // A record producer must never overwrite a retained executable descriptor,
 // constant template or an original consumer binding through an alias.
 uint64_t recordAddress=records.gpuAddress;
 if(!recordAddress||recordAddress>>40||records.length>((uint64_t(1)<<40)-recordAddress)){fail(error,@"Command IR record address span differs");return nil;}
 NSMutableArray*protectedBuffers=[NSMutableArray new];
 for(KPRecordedNativeCompute*r in plan.owners)[protectedBuffers addObjectsFromArray:@[r.constants,r.descriptor]];
 for(unsigned pass=0;pass<2;pass++){KPComputeICB*buffer=pass?(KPComputeICB*)destination:(KPComputeICB*)source;NSRange selected=pass?targetRange:range;for(NSUInteger i=selected.location;i<NSMaxRange(selected);i++)for(NSDictionary*binding in ((KPComputeICBCommand*)buffer.commands[i]).bindings.allValues)[protectedBuffers addObject:binding[@"buffer"]];}
 for(id<MTLBuffer>buffer in protectedBuffers){uint64_t address=buffer.gpuAddress;if(records==buffer||(recordAddress<address+buffer.length&&address<recordAddress+records.length)){fail(error,@"Command IR records alias an original binding/native command state");return nil;}}
 plan.commandIRLimits=[_device newBufferWithLength:range.length*32 options:MTLResourceStorageModeShared];
 plan.commandIRContext=[_device newBufferWithLength:sizeof(KPCommandContext)options:MTLResourceStorageModePrivate];
 if(!plan.commandIRLimits||!plan.commandIRContext){fail(error,@"Command IR catalogue/context allocation failed");return nil;}
 NSMutableArray*parameters=[NSMutableArray new],*addresses=[NSMutableArray new];
 for(NSUInteger i=0;i<range.length;i++){
  KPComputeICBCommand*c=((KPComputeICB*)source).commands[range.location+i];NSDictionary*binding=c.bindings[@2];id<MTLBuffer>buffer=binding[@"buffer"];uint64_t a=buffer.gpuAddress+[binding[@"offset"]unsignedIntegerValue];
  uint32_t row[8]={(uint32_t)c.groups.width,(uint32_t)c.local.width,(uint32_t)[c.threadgroupLengths[@0]unsignedIntegerValue],0,(uint32_t)a,(uint32_t)(a>>32),0,0};memcpy((char*)plan.commandIRLimits.contents+i*32,row,32);[parameters addObject:buffer];[addresses addObject:@(a)];
 }
 plan.commandIRParameters=[parameters copy];plan.commandIRParameterAddresses=[addresses copy];
 KPCommandContext context={KP_COMMAND_CONTEXT_MAGIC,KP_COMMAND_IR_VERSION,(uint32_t)targetRange.length,3,records.gpuAddress+offset,KP_COMMAND_RECORD_BYTES,(uint32_t)range.length};
 id<MTLBuffer>initial=[_device newBufferWithBytes:&context length:sizeof context options:MTLResourceStorageModeShared];id<MTLCommandBuffer>cb=[_queue commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];
 if(!initial||!b){fail(error,@"Command IR context initializer missing");return nil;}[b copyFromBuffer:initial sourceOffset:0 toBuffer:plan.commandIRContext destinationOffset:0 size:sizeof context];[b endEncoding];if(!complete(cb)){fail(error,@"Command IR context initialization failed");return nil;}
 plan.commandIRGeneration=YES;[_eventRows addObject:@{@"operation":@"prepare_GPU_command_IR",@"rows":@(targetRange.length),@"candidate_count":@(range.length),@"record_bytes":@128,@"record_CPU_read":@NO,@"uniform_1D_only":@YES}];return plan;
}
