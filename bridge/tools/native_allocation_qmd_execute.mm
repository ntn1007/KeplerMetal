// SPDX-License-Identifier: MIT
// Reuse read-only layout helpers. The uncommitted entry point is never called.
#define main KPQMDUncommittedEntry
#include "native_allocation_qmd_capture.mm"
#undef main

static NSArray *words128(NSData*d){NSMutableArray*a=[NSMutableArray array];for(unsigned i=0;i<32;i++)[a addObject:@(u32(d,4*i))];return a;}

int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);NSArray*parts=[mode componentsSeparatedByString:@":"];
 if(parts.count!=2||![@[@"native",@"reserved"]containsObject:parts[0]])return 1;BOOL corrected=[parts[0]isEqual:@"reserved"];NSString*name=parts[1];
 NSDictionary*manifest=json([NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"native-allocation-manifest.json"]]);NSDictionary*entry=manifest[@"certificates"][name];
 if(![entry isKindOfClass:NSDictionary.class])return 1;
 NSData*libraryData=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"control_flow.metallib"]];
 NSData*certificateData=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:entry[@"file"]]];NSDictionary*cert=json(certificateData);
 if(![sha(libraryData)isEqual:manifest[@"library_sha256"]]||![sha(certificateData)isEqual:entry[@"SHA256"]]||![cert[@"function"]isEqual:name])return 2;
 id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(d.registryID==4294968458&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"])device=d;
 NSString*driverHash=sha([NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"]);
 if(!device||![driverHash isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 NSError*error=nil;NSDictionary*proof=@{};id<MTLComputePipelineState>pipeline=nil;
 if(corrected)pipeline=KPCreateCertifiedNativeAllocationPipeline(device,libraryData,manifest[@"library_sha256"],certificateData,entry[@"SHA256"],&error,&proof);
 else {
  dispatch_data_t data=dispatch_data_create(libraryData.bytes,libraryData.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)libraryData.length;});
  id<MTLLibrary>library=[device newLibraryWithData:data error:&error];id<MTLFunction>function=[library newFunctionWithName:name];
  if(function)pipeline=[device newComputePipelineStateWithFunction:function error:&error];
 }
 if(!pipeline){emit(@{@"status":@"PIPELINE_REFUSED",@"mode":mode,@"error":error.description?:@"",@"import":proof?:@{},@"runs":@[]});return 3;}
 NSData*initial=variant(pipeline);NSArray*w=cert[@"metadata_words"];
 if(initial.length!=128||u64(initial,24)!=[cert[@"code_bytes"]unsignedIntegerValue]||u32(initial,48)!=[w[7]unsignedIntValue]||u32(initial,56)!=[w[14]unsignedIntValue])return 3;
 id<MTLCommandQueue>queue=[device newCommandQueue];NSMutableArray*runs=[NSMutableArray array];
 for(unsigned trial=0;trial<3;trial++){@autoreleasepool{
  const uint32_t groups=3,local=33,count=99;uint32_t seed=0x13579+trial*971,reserved=trial%3;uint32_t params[4]={seed,count,129,reserved};
  NSUInteger inputBytes=256+count*129*4,outputBytes=256+count*16;
  id<MTLBuffer>input=[device newBufferWithLength:inputBytes options:MTLResourceStorageModePrivate],output=[device newBufferWithLength:outputBytes options:MTLResourceStorageModePrivate];
  id<MTLBuffer>hi=[device newBufferWithLength:inputBytes options:MTLResourceStorageModeShared],ho=[device newBufferWithLength:outputBytes options:MTLResourceStorageModeShared],parameters=[device newBufferWithLength:512 options:MTLResourceStorageModeShared];
  if(!input||!output||!hi||!ho||!parameters)return 4;
  memset(hi.contents,0xa5,inputBytes);memset(ho.contents,0xa5,outputBytes);memset(parameters.contents,0xa5,512);memcpy(parameters.contents,params,sizeof(params));
  uint32_t*values=(uint32_t*)((char*)hi.contents+128);for(unsigned i=0;i<count*129;i++)values[i]=(i*1664525u+1013904223u)^seed;
  id<MTLCommandBuffer>init=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[init blitCommandEncoder];
  [blit copyFromBuffer:hi sourceOffset:0 toBuffer:input destinationOffset:0 size:inputBytes];[blit copyFromBuffer:ho sourceOffset:0 toBuffer:output destinationOffset:0 size:outputBytes];[blit endEncoding];[init commit];[init waitUntilCompleted];if(init.status!=MTLCommandBufferStatusCompleted)return 5;
  id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];
  [encoder setComputePipelineState:pipeline];[encoder setBuffer:input offset:128 atIndex:0];[encoder setBuffer:output offset:128 atIndex:1];[encoder setBuffer:parameters offset:0 atIndex:2];
  Cursor before=cursor(encoder);[encoder dispatchThreadgroups:MTLSizeMake(groups,1,1)threadsPerThreadgroup:MTLSizeMake(local,1,1)];Cursor after=cursor(encoder);
  BOOL comparable=before.valid&&after.valid&&before.push==after.push&&before.current&&after.current>before.current&&after.current<=before.end&&after.current-before.current<=65536;
  NSData*stream=comparable?readMemory(before.current,after.current-before.current):nil;NSString*commandFile=[NSString stringWithFormat:@"trial-%u.commands.bin",trial];
  if(!stream.length||![stream writeToFile:[out stringByAppendingPathComponent:commandFile]atomically:YES])return 6;
  NSData*again=readMemory(before.current,stream.length);BOOL unchanged=[again isEqual:stream];
  [encoder endEncoding];BOOL capturedUncommitted=command.status==MTLCommandBufferStatusNotEnqueued;if(!unchanged||!capturedUncommitted)return 6;
  [command commit];[command waitUntilCompleted];if(command.status!=MTLCommandBufferStatusCompleted)return 7;
  id<MTLCommandBuffer>read=[queue commandBuffer];blit=[read blitCommandEncoder];
  [blit copyFromBuffer:input sourceOffset:0 toBuffer:hi destinationOffset:0 size:inputBytes];[blit copyFromBuffer:output sourceOffset:0 toBuffer:ho destinationOffset:0 size:outputBytes];[blit endEncoding];[read commit];[read waitUntilCompleted];if(read.status!=MTLCommandBufferStatusCompleted)return 8;
  NSString*inputFile=[NSString stringWithFormat:@"trial-%u-input.bin",trial],*outputFile=[NSString stringWithFormat:@"trial-%u-output.bin",trial],*parameterFile=[NSString stringWithFormat:@"trial-%u-parameters.bin",trial];
  BOOL saved=[[NSData dataWithBytes:hi.contents length:inputBytes]writeToFile:[out stringByAppendingPathComponent:inputFile]atomically:YES]
   &&[[NSData dataWithBytes:ho.contents length:outputBytes]writeToFile:[out stringByAppendingPathComponent:outputFile]atomically:YES]
   &&[[NSData dataWithBytes:parameters.contents length:512]writeToFile:[out stringByAppendingPathComponent:parameterFile]atomically:YES];
  NSData*afterFields=variant(pipeline);if(!saved||afterFields.length!=128)return 9;
  [runs addObject:@{@"trial":@(trial),@"seed":@(seed),@"reserved":@(reserved),@"threads":@(count),@"groups":@(groups),@"local":@(local),@"stride":@129,@"input_bytes":@(inputBytes),@"output_bytes":@(outputBytes),@"parameters_bytes":@512,
    @"input_file":inputFile,@"output_file":outputFile,@"parameters_file":parameterFile,@"command_file":commandFile,@"command_bytes":@(stream.length),@"command_SHA256":sha(stream),@"stream_unchanged_on_immediate_recheck":@(unchanged),@"captured_before_commit":@(capturedUncommitted),@"before":info(before),@"after":info(after),
    @"input_GPU_address":@(input.gpuAddress),@"output_GPU_address":@(output.gpuAddress),@"parameters_GPU_address":@(parameters.gpuAddress),@"command_status":@(command.status),@"init_status":@(init.status),@"read_status":@(read.status),@"kernel_dispatches":@1,@"committed":@YES,
    @"variant_after_words_0_128":words128(afterFields),@"variant_after_SHA256":sha(afterFields)}];
 }}
 emit(@{@"status":@"COMPLETED",@"mode":mode,@"function":name,@"device":device.name,@"registry_id":@(device.registryID),@"driver_SHA256":driverHash,@"library_SHA256":sha(libraryData),@"certificate_SHA256":sha(certificateData),@"import":proof?:@{},
  @"variant_initial_words_0_128":words128(initial),@"variant_initial_SHA256":sha(initial),@"runs":runs,@"user_GPU_command_buffers":@9,@"user_compute_command_buffers":@3,@"user_blit_command_buffers":@6,
  @"CPU_expected_answers_uploaded":@NO,@"native_memory_written_by_probe":@NO,@"packet_replay":@NO,@"system_modified":@NO,@"performance_benchmark":@NO,
  @"scope":@"Unmodified own encoder bytes captured before ordinary Metal commit; DMA initialization/readback and numerical correctness checked separately. No packet writes or replay."});return 0;
}}
