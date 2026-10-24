// SPDX-License-Identifier: MIT
// Included after the ordinary producer, before record materialization.
struct AIRContext{uint32_t magic,version,capacity,bytes;uint64_t records,reserved;};
static_assert(sizeof(AIRContext)==32,"AIR context ABI");
bool resetDispatched=airDispatchesReset(mode);
NSMutableData *resetContext=bytes(160),*resetRoot=bytes(136),*resetIndices=bytes(144),*resetOutput=bytes(144);
AIRContext resetHeader={0x4b505243,1,4,64,buffers[@"records"].gpuAddress+64,0};
if([mode hasPrefix:@"air_bad_context"])resetHeader.magic^=1;
memcpy((char*)resetContext.mutableBytes+64,&resetHeader,32);
id<MTLBuffer>resetContextGPU=privateBuffer(@"reset-context",resetContext);
uint64_t resetContextAddress=resetContextGPU.gpuAddress+64;memcpy((char*)resetRoot.mutableBytes+64,&resetContextAddress,8);
id<MTLBuffer>resetRootGPU=privateBuffer(@"reset-root",resetRoot);
uint32_t resetIndexValues[4]={3,11,7,15};memcpy((char*)resetIndices.mutableBytes+64,resetIndexValues,16);
id<MTLBuffer>resetIndicesGPU=privateBuffer(@"reset-indices",resetIndices),resetOutputGPU=privateBuffer(@"reset-output",resetOutput);
if(resetDispatched){
    uint32_t resetConfig[4]={4,3,0,0};id<MTLComputeCommandEncoder>resetEncoder=[cb computeCommandEncoder];
    [resetEncoder setComputePipelineState:airResetPipeline];[resetEncoder setBuffer:resetRootGPU offset:64 atIndex:0];
    [resetEncoder setBuffer:resetOutputGPU offset:64 atIndex:1];[resetEncoder setBuffer:resetIndicesGPU offset:64 atIndex:2];[resetEncoder setBytes:resetConfig length:16 atIndex:3];
    [resetEncoder useResource:resetContextGPU usage:MTLResourceUsageRead];[resetEncoder useResource:buffers[@"records"]usage:MTLResourceUsageRead|MTLResourceUsageWrite];
    [resetEncoder dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[resetEncoder endEncoding];
}
NSArray *resetKeep=@[resetContextGPU,resetRootGPU,resetIndicesGPU,resetOutputGPU,buffers[@"records"],airResetPipeline];
[cb addCompletedHandler:^(id<MTLCommandBuffer>done){(void)resetKeep.count;}];
NSDictionary *resetRow=@{@"dispatched":@(resetDispatched),@"capacity":@4,@"count":@4,@"seed":@3,@"mask":@0,@"target_slot":@3,
    @"context_GPU_address":@(resetContextAddress),@"records_GPU_address":@(resetHeader.records),
    @"root_GPU_address":@(resetRootGPU.gpuAddress+64),@"context_storage_mode":@(resetContextGPU.storageMode),
    @"records_storage_mode":@(buffers[@"records"].storageMode),@"root_storage_mode":@(resetRootGPU.storageMode),
    @"indices_storage_mode":@(resetIndicesGPU.storageMode),@"output_storage_mode":@(resetOutputGPU.storageMode)};
