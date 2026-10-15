// SPDX-License-Identifier: MIT
// Shared GTX/M1 public-call selection; the caller uses normal Metal factories.
static NSUInteger receptionQueueKind=0,receptionEncoderKind=0;
static id<MTLCommandBuffer>receptionCommandBuffer(id<MTLCommandQueue>queue){
 if(!receptionQueueKind)return [queue commandBuffer];MTLCommandBufferDescriptor*p=[MTLCommandBufferDescriptor new];p.retainedReferences=YES;return [queue commandBufferWithDescriptor:p];
}
static id<MTLComputeCommandEncoder>receptionComputeEncoder(id<MTLCommandBuffer>buffer){
 if(!receptionEncoderKind)return [buffer computeCommandEncoder];
 if(receptionEncoderKind<3)return [buffer computeCommandEncoderWithDispatchType:receptionEncoderKind==1?MTLDispatchTypeSerial:MTLDispatchTypeConcurrent];
 MTLComputePassDescriptor*p=[MTLComputePassDescriptor computePassDescriptor];p.dispatchType=receptionEncoderKind==3?MTLDispatchTypeSerial:MTLDispatchTypeConcurrent;return [buffer computeCommandEncoderWithDescriptor:p];
}
