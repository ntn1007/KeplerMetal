// SPDX-License-Identifier: MIT
// This client constructs no GPU context header or GPU address root.
bool resetDispatched=airDispatchesReset(mode);
KPRenderCommandArgumentContext *recordArgumentContext=[scope newRenderCommandArgumentContextWithCommands:commands[0]stateCatalogue:catalogue commandRecords:buffers[@"records"]commandRecordsOffset:64 commandBuffer:cb error:&error];
require(recordArgumentContext!=nil,error.description.UTF8String?:"owned render context");
buffers[@"reset-context"]=recordArgumentContext.contextBuffer;
capture.readbacks[@"reset-context"]=[device newBufferWithLength:recordArgumentContext.contextBuffer.length options:MTLResourceStorageModeShared];
id<MTLArgumentEncoder>recordArgumentEncoder=nil;MTLArgument *recordArgumentReflection=nil;
NSString *recordGetter=@"function";
if([mode isEqual:@"arguments_device"]){
    MTLArgumentDescriptor *d=[MTLArgumentDescriptor argumentDescriptor];d.index=0;d.arrayLength=1;d.dataType=MTLDataTypeIndirectCommandBuffer;
    recordArgumentEncoder=[device newArgumentEncoderWithArguments:@[d]];recordGetter=@"device";
}else if([mode isEqual:@"arguments_reflection"]){
    recordArgumentEncoder=[recordProducerFunction newArgumentEncoderWithBufferIndex:0 reflection:&recordArgumentReflection];recordGetter=@"function_reflection";
}else recordArgumentEncoder=[recordProducerFunction newArgumentEncoderWithBufferIndex:0];
require(recordArgumentEncoder.encodedLength==8&&recordArgumentEncoder.alignment==8,"render record root shape");
id<MTLBuffer>resetRootGPU=[device newBufferWithLength:136 options:MTLResourceStorageModeShared];memset(resetRootGPU.contents,0xa5,136);
buffers[@"reset-root"]=resetRootGPU;capture.readbacks[@"reset-root"]=[device newBufferWithLength:136 options:MTLResourceStorageModeShared];
if([mode isEqual:@"arguments_reuse"]){
    id<MTLBuffer>spare=[device newBufferWithLength:136 options:MTLResourceStorageModeShared];memset(spare.contents,0xa5,136);
    buffers[@"reset-spare-root"]=spare;capture.readbacks[@"reset-spare-root"]=[device newBufferWithLength:136 options:MTLResourceStorageModeShared];
    [recordArgumentEncoder setArgumentBuffer:spare offset:64];[recordArgumentEncoder setIndirectCommandBuffer:commands[0]atIndex:0];
}
if([mode isEqual:@"arguments_arrays"]){
    [recordArgumentEncoder setArgumentBuffer:resetRootGPU startOffset:64 arrayElement:0];
    id<MTLIndirectCommandBuffer>values[]={commands[0]};[recordArgumentEncoder setIndirectCommandBuffers:values withRange:NSMakeRange(0,1)];
}else{[recordArgumentEncoder setArgumentBuffer:resetRootGPU offset:64];[recordArgumentEncoder setIndirectCommandBuffer:commands[0]atIndex:0];}
NSMutableData *resetIndices=bytes(144),*resetOutput=bytes(144);uint32_t resetIndexValues[4]={3,11,7,15};memcpy((char*)resetIndices.mutableBytes+64,resetIndexValues,16);
uint32_t resetSeed=3,resetOrder=0,resetSlot=3;
#if KP_TYPED_RENDER_DRAW
resetSeed=airDrawSeed(trial);resetOrder=airDrawOrder(mode);resetSlot=0;resetIndexValues[0]=0;memcpy((char*)resetIndices.mutableBytes+64,resetIndexValues,16);
#endif
id<MTLBuffer>resetIndicesGPU=privateBuffer(@"reset-indices",resetIndices),resetOutputGPU=privateBuffer(@"reset-output",resetOutput);
NSMutableArray *recordRefusals=[NSMutableArray new];
#include "RenderRecordArgumentsContracts.inc"
if(resetDispatched){
    uint32_t resetConfig[4]={4,resetSeed,0,resetOrder};id<MTLComputeCommandEncoder>resetEncoder=[cb computeCommandEncoder];
    [resetEncoder setComputePipelineState:recordProducerPipeline];
    if([mode isEqual:@"arguments_contracts"]&&trial==0){
        id<MTLBuffer>unexported=[device newBufferWithLength:136 options:MTLResourceStorageModeShared];memset(unexported.contents,0xa5,136);
        error=nil;BOOL value=[scope prepareRenderCommandArgumentContext:recordArgumentContext argumentBuffer:unexported offset:64 computeEncoder:resetEncoder commandBuffer:cb error:&error];recordRefuseBool(@"unexported_root",value,error);
        ((uint8_t*)resetRootGPU.contents)[64]^=1;
        error=nil;value=[scope prepareRenderCommandArgumentContext:recordArgumentContext argumentBuffer:resetRootGPU offset:64 computeEncoder:resetEncoder commandBuffer:cb error:&error];recordRefuseBool(@"tampered_root",value,error);recordRestoreRoot();
    }
    BOOL prepared=[scope prepareRenderCommandArgumentContext:recordArgumentContext argumentBuffer:resetRootGPU offset:64 computeEncoder:resetEncoder commandBuffer:cb error:&error];require(prepared,error.description.UTF8String?:"root resource preparation");
    if([mode isEqual:@"arguments_contracts"]&&trial==0){
        error=nil;BOOL value=[scope prepareRenderCommandArgumentContext:recordArgumentContext argumentBuffer:resetRootGPU offset:64 computeEncoder:resetEncoder commandBuffer:cb error:&error];recordRefuseBool(@"second_preparation",value,error);
        BOOL refused=NO;@try{[recordArgumentEncoder setIndirectCommandBuffer:commands[0]atIndex:0];}@catch(NSException*x){refused=YES;}require(refused,"prepared root setter refused");[recordRefusals addObject:@"setter_after_preparation"];
        [recordArgumentEncoder setArgumentBuffer:nil offset:0];
    }
    [resetEncoder setBuffer:resetOutputGPU offset:64 atIndex:1];[resetEncoder setBuffer:resetIndicesGPU offset:64 atIndex:2];[resetEncoder setBytes:resetConfig length:16 atIndex:3];
    [resetEncoder dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[resetEncoder endEncoding];
}
// Addresses below are observations for the independent oracle, never inputs
// to root/header construction or GPU state-choice decisions in this client.
NSDictionary *resetRow=@{@"dispatched":@(resetDispatched),@"capacity":@4,@"count":@4,@"seed":@(resetSeed),@"mask":@0,@"target_slot":@(resetSlot),@"order":@(resetOrder),
    @"context_GPU_address":@(recordArgumentContext.contextBuffer.gpuAddress+recordArgumentContext.contextOffset),
    @"records_GPU_address":@(buffers[@"records"].gpuAddress+64),@"root_GPU_address":@(resetRootGPU.gpuAddress+64),
    @"context_storage_mode":@(recordArgumentContext.contextBuffer.storageMode),@"records_storage_mode":@(buffers[@"records"].storageMode),
    @"root_storage_mode":@(resetRootGPU.storageMode),@"indices_storage_mode":@(resetIndicesGPU.storageMode),@"output_storage_mode":@(resetOutputGPU.storageMode),
    @"public_getter":recordGetter,@"encoded_length":@(recordArgumentEncoder.encodedLength),@"alignment":@(recordArgumentEncoder.alignment),
    @"reflection_requested":@(recordArgumentReflection!=nil),@"reflection_type":@(recordArgumentReflection?recordArgumentReflection.bufferDataType:0),
    @"root_refusals":recordRefusals,@"ordinary_pipeline":recordProducerProgramProof,@"client_GPU_address_construction":@NO};
