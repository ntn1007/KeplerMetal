// SPDX-License-Identifier: MIT
// Registered native function; only its two root-encoder getters are adapted.
NSData *recordProducerLibrary=load(assets,@"reset-lowered.metallib");
id<MTLFunction>recordProducerFunction=[scope newRenderCommandFunctionWithLibraryData:recordProducerLibrary expectedSHA256:sha(recordProducerLibrary) functionName:@"probe_boundary" rootBufferIndex:0 error:&error];
require(recordProducerFunction!=nil,error.description.UTF8String?:"render record function registration");
Class recordProducerNativeClass=class_getSuperclass(object_getClass(recordProducerFunction));
id<MTLComputePipelineState>recordProducerPipeline=[device newComputePipelineStateWithFunction:recordProducerFunction error:&error];
require(recordProducerPipeline!=nil,error.description.UTF8String?:"ordinary native render producer PSO");
NSDictionary *recordProducerProgramProof=nil;
require(KPCheckCertifiedResetPipeline(recordProducerPipeline,[assets stringByAppendingPathComponent:@"reset-lowered.certificate.json"],
    [airResetOutputDirectory stringByAppendingPathComponent:[NSString stringWithFormat:@"reset-native-frame-%u.bin",trial]],&recordProducerProgramProof,&error),error.description.UTF8String?:"ordinary native program certificate");
