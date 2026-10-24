// SPDX-License-Identifier: MIT
// Bounded CPU refusals. No malformed root is ever submitted to the GPU.
auto recordRefuseBool=[&](NSString *name,BOOL value,NSError *failure){require(!value&&failure!=nil,"expected render argument refusal");[recordRefusals addObject:name];};
auto recordRestoreRoot=[&](){[recordArgumentEncoder setArgumentBuffer:resetRootGPU offset:64];[recordArgumentEncoder setIndirectCommandBuffer:commands[0]atIndex:0];};
auto recordRefuseSetter=[&](NSString *name,void(^call)(void)){
    BOOL rejected=NO;@try{call();}@catch(NSException *exception){rejected=YES;}
    require(rejected,"expected render argument setter refusal");[recordRefusals addObject:name];recordRestoreRoot();
};
if([mode isEqual:@"arguments_contracts"]&&trial==0){
    id<MTLIndirectCommandBuffer>argumentTarget=commands[0],argumentOther=commands[1];
    error=nil;id bad=[scope newRenderCommandFunctionWithLibraryData:recordProducerLibrary expectedSHA256:@"0000000000000000000000000000000000000000000000000000000000000000" functionName:@"probe_boundary" rootBufferIndex:0 error:&error];recordRefuseBool(@"bad_library_pin",bad!=nil,error);
    error=nil;bad=[scope newRenderCommandFunctionWithLibraryData:recordProducerLibrary expectedSHA256:sha(recordProducerLibrary) functionName:@"probe_boundary" rootBufferIndex:1 error:&error];recordRefuseBool(@"bad_function_root_index",bad!=nil,error);
    auto contextRefused=[&](NSString *name,id<MTLIndirectCommandBuffer>target,id<MTLBuffer>recordBuffer,NSUInteger offset,id<MTLCommandBuffer>commandBuffer){NSError*failure=nil;id value=[scope newRenderCommandArgumentContextWithCommands:target stateCatalogue:catalogue commandRecords:recordBuffer commandRecordsOffset:offset commandBuffer:commandBuffer error:&failure];recordRefuseBool(name,value!=nil,failure);};
    contextRefused(@"duplicate_context",commands[0],buffers[@"records"],64,cb);
    contextRefused(@"wrong_execution_ICB",commands[1],buffers[@"records"],64,cb);
    contextRefused(@"record_offset_alignment",commands[0],buffers[@"records"],68,cb);
    contextRefused(@"short_record_buffer",commands[0],[device newBufferWithLength:255 options:MTLResourceStorageModePrivate],0,cb);
    id<MTLCommandQueue>otherQueue=[device newCommandQueue];contextRefused(@"wrong_queue",commands[0],buffers[@"records"],64,[otherQueue commandBuffer]);
    contextRefused(@"unretained_CB",commands[0],buffers[@"records"],64,[queue commandBufferWithUnretainedReferences]);
    recordRefuseSetter(@"wrong_setter_index",^{[recordArgumentEncoder setIndirectCommandBuffer:argumentTarget atIndex:1];});
    recordRefuseSetter(@"unprepared_ICB",^{[recordArgumentEncoder setIndirectCommandBuffer:argumentOther atIndex:0];});
    id<MTLBuffer>privateRoot=[device newBufferWithLength:136 options:MTLResourceStorageModePrivate];
    recordRefuseSetter(@"private_root",^{[recordArgumentEncoder setArgumentBuffer:privateRoot offset:64];});
    recordRefuseSetter(@"misaligned_root",^{[recordArgumentEncoder setArgumentBuffer:resetRootGPU offset:65];});
    id<MTLBuffer>shortRoot=[device newBufferWithLength:7 options:MTLResourceStorageModeShared];
    recordRefuseSetter(@"short_root",^{[recordArgumentEncoder setArgumentBuffer:shortRoot offset:0];});
    recordRefuseSetter(@"unsupported_buffer_setter",^{[recordArgumentEncoder setBuffer:resetRootGPU offset:64 atIndex:0];});
    BOOL offThread=NO;std::thread worker([&]{@autoreleasepool{@try{[recordArgumentEncoder setIndirectCommandBuffer:commands[0]atIndex:0];}@catch(NSException*x){offThread=YES;}}});worker.join();require(offThread,"off-thread setter must refuse");[recordRefusals addObject:@"off_thread_ICB"];recordRestoreRoot();
    MTLArgumentDescriptor*d=[MTLArgumentDescriptor argumentDescriptor];d.index=1;d.dataType=MTLDataTypeIndirectCommandBuffer;
    recordRefuseSetter(@"wrong_device_descriptor_index",^{[device newArgumentEncoderWithArguments:@[d]];});d.index=0;d.arrayLength=2;
    recordRefuseSetter(@"wrong_device_descriptor_array",^{[device newArgumentEncoderWithArguments:@[d]];});
    d=[MTLArgumentDescriptor argumentDescriptor];d.index=0;d.dataType=MTLDataTypePointer;
    id<MTLArgumentEncoder>ordinary=[device newArgumentEncoderWithArguments:@[d]];require(ordinary.encodedLength==8&&ordinary.alignment==8,"ordinary pointer factory preserved");
    MTLArgument *ordinaryReflection=nil;ordinary=[recordProducerFunction newArgumentEncoderWithBufferIndex:1 reflection:&ordinaryReflection];
    require(ordinary.encodedLength==0&&ordinary.alignment==1&&ordinaryReflection.bufferDataType==MTLDataTypeUInt&&ordinaryReflection.bufferDataSize==4,"non-root getter preserved");
}
