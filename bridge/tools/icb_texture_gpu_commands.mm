// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#import "KeplerDriverProfile.h"
#import "KeplerCPUICB.h"
#include <CommonCrypto/CommonDigest.h>
#import <objc/runtime.h>
#include <vector>
#include <cstring>
#include <cstdio>
struct DirectArguments{MTLResourceID image,sampling;uint64_t input;};
static_assert(sizeof(DirectArguments)==24,"Direct resource-argument ABI");
static void emit(id d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
static NSString*sha(NSData*d){unsigned char b[32];CC_SHA256(d.bytes,(CC_LONG)d.length,b);NSMutableString*s=[NSMutableString new];for(unsigned char x:b)[s appendFormat:@"%02x",x];return s;}
static uint64_t bits(MTLResourceID value){uint64_t word;memcpy(&word,&value,8);return word;}
int main(int argc,char**argv){@autoreleasepool{
    if(argc!=4)return 1;NSString*mode=@(argv[2]),*out=@(argv[3]);
    NSArray *modes=@[@"gpu",@"gpu_wrong_texture",@"gpu_wrong_sampler",@"gpu_wrong_buffer",@"gpu_no_consumer",@"gpu_no_producer"];
    if(![modes containsObject:mode])return 1;
    BOOL producer=![mode isEqual:@"gpu_no_producer"],consumer=![mode isEqual:@"gpu_no_consumer"],dispatch=producer&&consumer;

    id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSDictionary*identity=KPKepler880MIdentity(d);if(!identity||!KPKeplerDriverHashIsQualified(sha([NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"])))return 2;
    NSError*error=nil;id<MTLLibrary>library=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])]error:&error];
    if(!library){emit(@{@"stage":@"library",@"error":error.description?:@"nil"});return 3;}
    id<MTLFunction>function=[library newFunctionWithName:@"sample_icb_arguments"];if(!function)return 3;
    MTLComputePipelineReflection*reflection=nil;
    id<MTLComputePipelineState>pipeline=[d newComputePipelineStateWithFunction:function options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:&error];
    if(!pipeline){emit(@{@"stage":@"pipeline",@"error":error.description?:@"nil"});return 3;}
    id<MTLArgumentEncoder>ae=[function newArgumentEncoderWithBufferIndex:0];
    NSMutableArray*layout=[NSMutableArray new];
    for(MTLArgument*a in reflection.arguments)if(a.type==MTLArgumentTypeBuffer&&a.index==0)
        for(MTLStructMember*m in a.bufferStructType.members)[layout addObject:@{@"name":m.name,@"offset":@(m.offset),@"type":@(m.dataType)}];
    if(ae.encodedLength!=24||ae.alignment!=8||layout.count!=3||[layout[0][@"offset"]unsignedIntegerValue]!=0||[layout[1][@"offset"]unsignedIntegerValue]!=8||[layout[2][@"offset"]unsignedIntegerValue]!=16||pipeline.threadExecutionWidth!=32||pipeline.maxTotalThreadsPerThreadgroup<32){emit(@{@"stage":@"ABI",@"layout":layout,@"encoded_length":@(ae.encodedLength),@"alignment":@(ae.alignment)});return 4;}
    id<MTLTexture>textures[2],parents[2];id<MTLSamplerState>samplers[2];
    for(unsigned k=0;k<2;k++){
        MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:k?8:4 height:k?8:4 mipmapped:k!=0];td.storageMode=MTLStorageModeManaged;td.usage=MTLTextureUsageShaderRead|MTLTextureUsagePixelFormatView;
        parents[k]=[d newTextureWithDescriptor:td];if(!parents[k])return 5;
        for(unsigned level=0;level<parents[k].mipmapLevelCount;level++){
            unsigned side=MAX(1u,unsigned(parents[k].width)>>level);std::vector<unsigned char>texels(side*side*4);
            unsigned bias=k?(level==1?91:202+level*7):13;
            for(unsigned y=0;y<side;y++)for(unsigned x=0;x<side;x++)for(unsigned c=0;c<4;c++)texels[(y*side+x)*4+c]=(x*47+y*29+c*37+bias)&255;
            [parents[k]replaceRegion:MTLRegionMake2D(0,0,side,side)mipmapLevel:level withBytes:texels.data()bytesPerRow:side*4];
        }
        textures[k]=k?[parents[k]newTextureViewWithPixelFormat:MTLPixelFormatRGBA8Unorm textureType:MTLTextureType2D levels:NSMakeRange(1,1)slices:NSMakeRange(0,1)]:parents[k];
        MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];sd.minFilter=MTLSamplerMinMagFilterNearest;sd.magFilter=MTLSamplerMinMagFilterNearest;sd.normalizedCoordinates=YES;
        sd.sAddressMode=sd.tAddressMode=k?MTLSamplerAddressModeRepeat:MTLSamplerAddressModeClampToEdge;sd.supportArgumentBuffers=YES;samplers[k]=[d newSamplerStateWithDescriptor:sd];
        if(!textures[k]||!samplers[k]||textures[k].width!=4||textures[k].height!=4||textures[k].mipmapLevelCount!=1)return 5;
    }
    id<MTLCommandQueue>queue=[d newCommandQueue];KPCPUICBScope*scope=nil;{NSData*data=[NSData dataWithContentsOfFile:@(argv[1])],*manifest=[NSData dataWithContentsOfFile:[[@(argv[1])stringByDeletingLastPathComponent]stringByAppendingPathComponent:@"consumer-profile.json"]];scope=[KPCPUICBScope installOnDevice:d queue:queue libraryData:data expectedSHA256:sha(data)manifestData:manifest expectedManifestSHA256:sha(manifest)error:&error];if(!scope){emit(@{@"failure":@"registration",@"error":error.description?:@""});return 7;}pipeline=[scope pipelineForFunction:@"sample_icb_arguments"];}
    NSString *assets=[@(argv[1])stringByDeletingLastPathComponent];
    for(NSArray *a in @[@[@"gpu_command_selector.metallib",@0],@[@"gpu_command_geometry.metallib",@1],@[@"gpu_command_bindings.metallib",@2],@[@"materializer.metallib",@3]]){
        NSData *b=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:a[0]]];BOOL enabled=NO;
        switch([a[1]intValue]){
            case 0:enabled=[scope enableGPUCommandSelectionWithLibraryData:b expectedSHA256:sha(b)error:&error];break;
            case 1:enabled=[scope enableGPUCommandGeometryWithLibraryData:b expectedSHA256:sha(b)error:&error];break;
            case 2:enabled=[scope enableGPUCommandBindingsWithLibraryData:b expectedSHA256:sha(b)error:&error];break;
            case 3:enabled=[scope enableGPUCommandIRv2WithLibraryData:b expectedSHA256:sha(b)error:&error];break;
        }
        if(!enabled){emit(@{@"failure":@"enable",@"error":error.description?:@""});return 7;}
    }
    NSData *producerData=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"producer.metallib"]];
    if(![scope registerNativeSourceCommandIRLibraryData:producerData expectedSHA256:sha(producerData) functionNames:@[@"encode_image_command"] reusableContexts:NO error:&error]){emit(@{@"failure":@"library_registration",@"error":error.description?:@""});return 7;}
    id<MTLLibrary>producerLibrary=[d newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"producer.metallib"]]error:&error];
    id<MTLFunction>producerFunction=[producerLibrary newFunctionWithName:@"encode_image_command"];
    id<MTLComputePipelineState>writer=producerFunction?[d newComputePipelineStateWithFunction:producerFunction error:&error]:nil;
    if(!writer||writer.threadExecutionWidth!=32||writer.maxTotalThreadsPerThreadgroup<32){emit(@{@"failure":@"producer_pipeline",@"error":error.description?:@""});return 7;}
    NSMutableArray*runs=[NSMutableArray new];BOOL ok=YES;
    const uint32_t sentinel=0xd15ea5ed;const unsigned counts[3]={16,65,257};
    for(unsigned trial=0;trial<3;trial++){
        unsigned n=counts[trial],seed=0x125ab700u+trial*97u;NSUInteger bytes=(((n+31)/32)*32+8)*16;
        id<MTLBuffer>inputs[2];std::vector<uint32_t>values(n+32);
        for(unsigned k=0;k<2;k++){for(unsigned i=0;i<values.size();i++)values[i]=(i*747796405u+seed)^0x12345678u^(k?0x2468ace1u:0);inputs[k]=[d newBufferWithBytes:values.data()length:values.size()*4 options:MTLResourceStorageModeShared];}
        id<MTLBuffer>root=[d newBufferWithLength:152 options:MTLResourceStorageModeShared];if(!root||!inputs[0]||!inputs[1])return 5;memset(root.contents,0xa5,root.length);
        unsigned ti=[mode containsString:@"wrong_texture"]?1:0,si=[mode containsString:@"wrong_sampler"]?1:0,bi=[mode containsString:@"wrong_buffer"]?1:0;
        [ae setArgumentBuffer:root offset:64];[ae setTexture:textures[ti]atIndex:0];[ae setSamplerState:samplers[si]atIndex:1];[ae setBuffer:inputs[bi]offset:32 atIndex:2];
        NSData*nativeBytes=[NSData dataWithBytes:(char*)root.contents+64 length:24];
        DirectArguments direct={textures[ti].gpuResourceID,samplers[si].gpuResourceID,inputs[bi].gpuAddress+32};
        id<MTLBuffer>alternateRoot=[d newBufferWithLength:152 options:MTLResourceStorageModeShared],alternateGPU=[d newBufferWithLength:152 options:MTLResourceStorageModePrivate],alternateReadback=[d newBufferWithLength:152 options:MTLResourceStorageModeShared];
        if(!alternateRoot||!alternateGPU||!alternateReadback)return 5;memset(alternateRoot.contents,0xa5,152);
        [ae setArgumentBuffer:alternateRoot offset:64];[ae setTexture:textures[ti^1]atIndex:0];[ae setSamplerState:samplers[si^1]atIndex:1];[ae setBuffer:inputs[bi^1]offset:32 atIndex:2];
        NSData *alternateNative=[NSData dataWithBytes:(char*)alternateRoot.contents+64 length:24];
        DirectArguments alternateIDs={textures[ti^1].gpuResourceID,samplers[si^1].gpuResourceID,inputs[bi^1].gpuAddress+32};
        unsigned bank=(n^seed^trial)&1u; // CPU oracle only; never supplied as a resolved choice.

        // Both paths preserve the complete native argument encoding.
        NSData*encoded=[NSData dataWithBytes:(char*)root.contents+64 length:24];
        std::vector<uint32_t>initial(bytes/4,sentinel);id<MTLBuffer>upload=[d newBufferWithBytes:initial.data()length:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer>gpu=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate],readback=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];
        if(!inputs[0]||!inputs[1]||!root||!upload||!gpu||!readback)return 5;
        // Keep CB2 at offset0: the current exact native transport qualifies
        // this512-byte constant-bank binding; nonzero CB2 offsets are separate.
        id<MTLBuffer>gpuRoot=[d newBufferWithLength:root.length options:MTLResourceStorageModePrivate],rootReadback=[d newBufferWithLength:root.length options:MTLResourceStorageModeShared],parameters=[d newBufferWithLength:512 options:MTLResourceStorageModeShared];if(!gpuRoot||!rootReadback||!parameters)return 5;memset(parameters.contents,0xa5,parameters.length);uint32_t meta[4]={n,seed,trial,0};memcpy(parameters.contents,meta,sizeof meta);uint64_t alternateAddress=alternateGPU.gpuAddress+64;memcpy((char*)parameters.contents+16,&alternateAddress,8);
        id<MTLBuffer>dummyRoot=[d newBufferWithLength:152 options:MTLResourceStorageModePrivate],dummyOutput=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate];
        id<MTLBuffer>records=[d newBufferWithLength:256 options:MTLResourceStorageModePrivate],recordUpload=[d newBufferWithLength:256 options:MTLResourceStorageModeShared],recordReadback=[d newBufferWithLength:256 options:MTLResourceStorageModeShared];
        if(!dummyRoot||!dummyOutput||!records||!recordUpload||!recordReadback)return 5;
        memset(recordUpload.contents,0xa5,256);memset((char*)recordUpload.contents+64,0,128);
        MTLIndirectCommandBufferDescriptor *desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=3;
        id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:2 options:MTLResourceStorageModeShared];
        for(unsigned slot=0;slot<2;slot++){
            id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:slot];[c setComputePipelineState:pipeline];[c setKernelBuffer:dummyRoot offset:64 atIndex:0];[c setKernelBuffer:dummyOutput offset:64 atIndex:1];[c setKernelBuffer:parameters offset:0 atIndex:2];[c concurrentDispatchThreadgroups:MTLSizeMake((n+31)/32,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];
        }
        if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,2)error:&error]){emit(@{@"failure":@"preparation",@"error":error.description?:@""});return 8;}
        KPGPUCommandSelection *plan=[scope newGPUStableCommandIRFromBuffer:icb sourceRange:NSMakeRange(0,1)destination:icb destinationRange:NSMakeRange(1,1)resources:@[@{@"bindings":@[@{@"buffer":gpuRoot,@"offset":@64},@{@"buffer":gpu,@"offset":@64}]},@{@"bindings":@[@{@"buffer":alternateGPU,@"offset":@64},@{@"buffer":gpu,@"offset":@64}]}]records:records recordOffset:64 error:&error];
        if(!plan){emit(@{@"failure":@"plan",@"error":error.description?:@""});return 8;}
        id<MTLArgumentEncoder>producerAE=trial%2?[producerFunction newArgumentEncoderWithBufferIndex:0 reflection:nil]:[producerFunction newArgumentEncoderWithBufferIndex:0];
        if(producerAE.encodedLength!=40||producerAE.alignment!=8)return 8;
        id<MTLBuffer>producerRoot=[d newBufferWithLength:168 options:MTLResourceStorageModeShared];if(!producerRoot)return 5;memset(producerRoot.contents,0xa5,168);
        [producerAE setArgumentBuffer:producerRoot offset:64];[producerAE setIndirectCommandBuffer:icb atIndex:0];[producerAE setComputePipelineState:pipeline atIndex:1];[producerAE setBuffer:gpuRoot offset:64 atIndex:2];[producerAE setBuffer:gpu offset:64 atIndex:3];[producerAE setBuffer:parameters offset:0 atIndex:4];
        if(![plan validateCommandIRArgumentBindings:&error]){emit(@{@"failure":@"producer_arguments",@"error":error.description?:@""});return 8;}
        id<MTLBuffer>witness=plan.generatedGeometry,witnessHost=[d newBufferWithLength:witness.length options:MTLResourceStorageModeShared];
        id<MTLBuffer>counts=plan.invocationCounts,countsHost=[d newBufferWithLength:counts.length options:MTLResourceStorageModeShared];
        // These are owned plan allocations, observed only after the consumer.
        NSArray *targetRecords=[plan valueForKey:@"targetRecords"];
        id<MTLBuffer>nativeConstants=[targetRecords[0]valueForKey:@"constants"],nativeQMD=[targetRecords[0]valueForKey:@"descriptor"],context=[plan valueForKey:@"commandIRContext"];
        id<MTLBuffer>constantsHost=[d newBufferWithLength:nativeConstants.length options:MTLResourceStorageModeShared],qmdHost=[d newBufferWithLength:nativeQMD.length options:MTLResourceStorageModeShared],contextHost=[d newBufferWithLength:context.length options:MTLResourceStorageModeShared];
        if(!witnessHost||!countsHost||!constantsHost||!qmdHost||!contextHost)return 5;
        id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];[blit copyFromBuffer:upload sourceOffset:0 toBuffer:gpu destinationOffset:0 size:bytes];[blit copyFromBuffer:root sourceOffset:0 toBuffer:gpuRoot destinationOffset:0 size:root.length];[blit copyFromBuffer:alternateRoot sourceOffset:0 toBuffer:alternateGPU destinationOffset:0 size:152];[blit copyFromBuffer:recordUpload sourceOffset:0 toBuffer:records destinationOffset:0 size:256];[blit endEncoding];
        if(producer){id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:writer];[e setBuffer:producerRoot offset:64 atIndex:0];for(id<MTLBuffer>r in plan.commandIRProducerResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];NSArray *keep=@[plan.commandIRProducerResources,producerRoot,writer];[cb addCompletedHandler:^(id<MTLCommandBuffer>done){(void)keep.count;}];}
        if(![plan encodeCommandIRInCommandBuffer:cb afterProducer:producer?cb:nil error:&error]){emit(@{@"failure":@"materializer",@"error":error.description?:@""});return 8;}
        if(consumer){id<MTLComputeCommandEncoder>ce=[cb computeCommandEncoder];[ce setComputePipelineState:pipeline];[ce setBuffer:gpuRoot offset:64 atIndex:0];[ce setBuffer:gpu offset:64 atIndex:1];[ce setBuffer:parameters offset:0 atIndex:2];
            for(unsigned k=0;k<2;k++){[ce useResource:textures[k]usage:MTLResourceUsageRead];[ce useResource:parents[k]usage:MTLResourceUsageRead];[ce useResource:inputs[k]usage:MTLResourceUsageRead];[ce useResource:alternateGPU usage:MTLResourceUsageRead];}
            if(![scope adaptComputeEncoder:ce error:&error])return 8;@try{[ce executeCommandsInBuffer:icb withRange:NSMakeRange(1,1)];}@catch(NSException*x){[ce endEncoding];emit(@{@"failure":@"execution",@"error":x.reason?:@""});return 8;}[ce endEncoding];}
        blit=[cb blitCommandEncoder];[blit copyFromBuffer:gpu sourceOffset:0 toBuffer:readback destinationOffset:0 size:bytes];[blit copyFromBuffer:gpuRoot sourceOffset:0 toBuffer:rootReadback destinationOffset:0 size:root.length];[blit copyFromBuffer:alternateGPU sourceOffset:0 toBuffer:alternateReadback destinationOffset:0 size:152];[blit copyFromBuffer:records sourceOffset:0 toBuffer:recordReadback destinationOffset:0 size:256];[blit copyFromBuffer:witness sourceOffset:0 toBuffer:witnessHost destinationOffset:0 size:witness.length];for(NSArray *pair in @[@[counts,countsHost],@[nativeConstants,constantsHost],@[nativeQMD,qmdHost],@[context,contextHost]]){id<MTLBuffer>src=pair[0],dst=pair[1];[blit copyFromBuffer:src sourceOffset:0 toBuffer:dst destinationOffset:0 size:src.length];}[blit endEncoding];[cb commit];[cb waitUntilCompleted];
        if(cb.status!=MTLCommandBufferStatusCompleted){emit(@{@"stage":@"completion",@"error":cb.error.description?:@"nil",@"command_status":@(cb.status)});return 6;}
        const uint32_t*actual=(const uint32_t*)((char*)readback.contents+64);unsigned bad=0,guards=0;for(unsigned i=0;i<bytes/4;i++)if(i<16||i>=16+n*4)guards+=((uint32_t*)readback.contents)[i]!=sentinel;
        for(unsigned i=0;i<n;i++){
            int x=int((i*3+trial)%12)-4,y=int((i*5+trial*2)%12)-4;x=(si^bank)?((x%4+4)%4):MAX(0,MIN(3,x));y=(si^bank)?((y%4+4)%4):MAX(0,MIN(3,y));
            uint32_t value=((i+8)*747796405u+seed)^0x12345678u^((bi^bank)?0x2468ace1u:0);uint32_t witness[4]={value^seed,i*3u,value*5u+trial,0xc0010000u^i^0x00040104u};
            for(unsigned c=0;c<4;c++){uint32_t expected=dispatch?uint32_t((x*47+y*29+c*37+((ti^bank)?91:13))&255)^witness[c]:sentinel;if(actual[i*4+c]!=expected)bad++;}
        }
        unsigned rootGuards=0;for(unsigned i=0;i<152;i++)rootGuards+=((unsigned char*)rootReadback.contents)[i]!=((unsigned char*)root.contents)[i];for(unsigned i=0;i<64;i++)rootGuards+=((unsigned char*)root.contents)[i]!=0xa5||((unsigned char*)root.contents)[88+i]!=0xa5;
        for(unsigned i=0;i<152;i++)rootGuards+=((unsigned char*)alternateReadback.contents)[i]!=((unsigned char*)alternateRoot.contents)[i];
        NSString*name=[NSString stringWithFormat:@"trial-%u",trial];[[NSData dataWithBytes:readback.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".output.bin"]]atomically:YES];
        [[NSData dataWithBytes:root.contents length:root.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".root.bin"]]atomically:YES];
        [[NSData dataWithBytes:rootReadback.contents length:rootReadback.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".private-root.bin"]]atomically:YES];
        [[NSData dataWithBytes:parameters.contents length:parameters.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".parameters.bin"]]atomically:YES];
        for(unsigned k=0;k<2;k++)[[NSData dataWithBytes:inputs[k].contents length:inputs[k].length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingFormat:@".input-%u.bin",k]]atomically:YES];
        [[NSData dataWithBytes:recordReadback.contents length:256]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".records.bin"]]atomically:YES];
        [[NSData dataWithBytes:witnessHost.contents length:witnessHost.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".witness.bin"]]atomically:YES];
        [[NSData dataWithBytes:producerRoot.contents length:producerRoot.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".producer-root.bin"]]atomically:YES];
        for(NSArray *pair in @[@[@"counts",countsHost],@[@"CB1",constantsHost],@[@"QMD",qmdHost],@[@"context",contextHost]]){id<MTLBuffer>h=pair[1];[[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingFormat:@".%@.bin",pair[0]]]atomically:YES];}
        [[NSData dataWithBytes:alternateRoot.contents length:152]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".alternate-root.bin"]]atomically:YES];
        [[NSData dataWithBytes:alternateReadback.contents length:152]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".alternate-private-root.bin"]]atomically:YES];
        [runs addObject:@{@"expected_GPU_bank":@(bank),@"context_GPU_address":@(context.gpuAddress),@"records_GPU_address_plus_offset":@(records.gpuAddress+64),@"argument_root_GPU_addresses_plus_offsets":@[@(gpuRoot.gpuAddress+64),@(alternateAddress)],@"alternate_native_bytes_base64":[alternateNative base64EncodedStringWithOptions:0],@"alternate_texture_ID":@(bits(alternateIDs.image)),@"alternate_sampler_ID":@(bits(alternateIDs.sampling)),@"alternate_input_GPU_address_plus_offset":@(alternateIDs.input),@"plan_events":plan.events,@"root_GPU_address_plus_offset":@(gpuRoot.gpuAddress+64),@"output_GPU_address_plus_offset":@(gpu.gpuAddress+64),@"parameters_GPU_address":@(parameters.gpuAddress),@"trial":@(trial),@"threads":@(n),@"seed":@(seed),@"texture":@(ti),@"sampler":@(si),@"input":@(bi),@"mismatches":@(bad),@"output_guard_mismatches":@(guards),@"root_guard_mismatches":@(rootGuards),@"command_status":@(cb.status),@"native_bytes_base64":[nativeBytes base64EncodedStringWithOptions:0],@"encoded_bytes_base64":[encoded base64EncodedStringWithOptions:0],@"texture_ID":@(bits(direct.image)),@"sampler_ID":@(bits(direct.sampling)),@"input_GPU_address_plus_offset":@(direct.input)}];
        ok&=!bad&&!guards&&!rootGuards;
    }
    if(scope)[scope restore];
    id<MTLArgumentEncoder>restoredEncoder=[producerFunction newArgumentEncoderWithBufferIndex:0];
    BOOL restoredNativeEncoder=[NSStringFromClass(object_getClass(restoredEncoder))isEqual:@"NVMTLIndirectArgumentEncoder"]&&restoredEncoder.encodedLength==40;
    if(!restoredNativeEncoder)return 11;
    emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":identity,@"mode":mode,@"runs":runs,@"argument_layout":layout,@"status":ok?@"PASS":@"FAIL",@"user_dispatches":dispatch?@3:@0,@"native_shader":@YES,@"CPU_ICB":@NO,@"GPU_generated_commands":@YES,@"native_library_factories":@YES,@"manual_function_registrations":@0,@"native_argument_encoder_restored":@(restoredNativeEncoder),@"producer_dispatches":producer?@3:@0,@"materializer_dispatches":@3,@"consumer_encoding_calls":consumer?@3:@0,@"producer_root_bytes":@40,@"producer_library_SHA256":sha(producerData),@"interposition":@YES,@"scope_events":scope.events?:@[],@"library_SHA256":sha([NSData dataWithContentsOfFile:@(argv[1])]),@"performance_benchmark":@NO});return ok?0:10;
}}
