// SPDX-License-Identifier: MIT
// Shared test helper: procedural inputs only, no CPU expected output uploaded.
struct KPAllocationParams {uint32_t seed,count,stride,reserved;};
static NSDictionary*KPRunAllocationKernel(id<MTLDevice>d,id<MTLComputePipelineState>pso,
 NSString*out,NSString*prefix,unsigned depth) {
 KPAllocationParams p={0x13579,33,129,2};NSUInteger inBytes=256+p.count*p.stride*4,outBytes=256+p.count*16;
 id<MTLBuffer>input=[d newBufferWithLength:inBytes options:MTLResourceStorageModePrivate];
 id<MTLBuffer>output=[d newBufferWithLength:outBytes options:MTLResourceStorageModePrivate];
 id<MTLBuffer>hi=[d newBufferWithLength:inBytes options:MTLResourceStorageModeShared];
 id<MTLBuffer>ho=[d newBufferWithLength:outBytes options:MTLResourceStorageModeShared];
 id<MTLBuffer>params=[d newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared];
 if(!input||!output||!hi||!ho||!params||pso.maxTotalThreadsPerThreadgroup<33)return nil;
 memset(hi.contents,0xa5,inBytes);memset(ho.contents,0xa5,outBytes);
 uint32_t*v=(uint32_t*)((uint8_t*)hi.contents+128);for(unsigned i=0;i<p.count*p.stride;i++)v[i]=(i*1664525u+1013904223u)^p.seed;
 id<MTLCommandQueue>queue=[d newCommandQueue];id<MTLCommandBuffer>cb=[queue commandBuffer];
 id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];
 [b copyFromBuffer:hi sourceOffset:0 toBuffer:input destinationOffset:0 size:inBytes];
 [b copyFromBuffer:ho sourceOffset:0 toBuffer:output destinationOffset:0 size:outBytes];[b endEncoding];
 id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:pso];
 [e setBuffer:input offset:128 atIndex:0];[e setBuffer:output offset:128 atIndex:1];[e setBuffer:params offset:0 atIndex:2];
 [e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(33,1,1)];[e endEncoding];
 b=[cb blitCommandEncoder];[b copyFromBuffer:input sourceOffset:0 toBuffer:hi destinationOffset:0 size:inBytes];
 [b copyFromBuffer:output sourceOffset:0 toBuffer:ho destinationOffset:0 size:outBytes];[b endEncoding];
 [cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted)return nil;
 NSString*inf=[prefix stringByAppendingString:@"-input.bin"],*ouf=[prefix stringByAppendingString:@"-output.bin"];
 if(![[NSData dataWithBytes:hi.contents length:inBytes]writeToFile:[out stringByAppendingPathComponent:inf]atomically:YES]||
    ![[NSData dataWithBytes:ho.contents length:outBytes]writeToFile:[out stringByAppendingPathComponent:ouf]atomically:YES])return nil;
 return @{@"kind":@"native",@"depth":@(depth),@"threads":@33,@"local":@33,@"groups":@1,
  @"seed":@(p.seed),@"stride":@129,@"reserved":@2,@"input_file":inf,@"output_file":ouf,
  @"input_bytes":@(inBytes),@"output_bytes":@(outBytes),@"command_status":@(cb.status),@"kernel_dispatches":@1};
}
