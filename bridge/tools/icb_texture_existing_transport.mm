// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#import "KeplerDriverProfile.h"
#import "KeplerCPUICB.h"
#include <CommonCrypto/CommonDigest.h>
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
    NSArray *modes=@[@"native",@"native_wrong_texture",@"native_wrong_sampler",@"native_wrong_buffer",@"native_no_dispatch",@"cpu",@"cpu_wrong_texture",@"cpu_wrong_sampler",@"cpu_wrong_buffer",@"cpu_no_dispatch"];
    if(![modes containsObject:mode])return 1;
    BOOL cpu=[mode hasPrefix:@"cpu"],dispatch=![mode containsString:@"no_dispatch"];

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
    id<MTLCommandQueue>queue=[d newCommandQueue];KPCPUICBScope*scope=nil;if(cpu){NSData*data=[NSData dataWithContentsOfFile:@(argv[1])],*manifest=[NSData dataWithContentsOfFile:[[@(argv[1])stringByDeletingLastPathComponent]stringByAppendingPathComponent:@"consumer-profile.json"]];scope=[KPCPUICBScope installOnDevice:d queue:queue libraryData:data expectedSHA256:sha(data)manifestData:manifest expectedManifestSHA256:sha(manifest)error:&error];if(!scope){emit(@{@"failure":@"registration",@"error":error.description?:@""});return 7;}pipeline=[scope pipelineForFunction:@"sample_icb_arguments"];}NSMutableArray*runs=[NSMutableArray new];BOOL ok=YES;
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
        // Both paths preserve the complete native argument encoding.
        NSData*encoded=[NSData dataWithBytes:(char*)root.contents+64 length:24];
        std::vector<uint32_t>initial(bytes/4,sentinel);id<MTLBuffer>upload=[d newBufferWithBytes:initial.data()length:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer>gpu=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate],readback=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];
        if(!inputs[0]||!inputs[1]||!root||!upload||!gpu||!readback)return 5;
        // Keep CB2 at offset0: the current exact native transport qualifies
        // this512-byte constant-bank binding; nonzero CB2 offsets are separate.
        id<MTLBuffer>gpuRoot=[d newBufferWithLength:root.length options:MTLResourceStorageModePrivate],rootReadback=[d newBufferWithLength:root.length options:MTLResourceStorageModeShared],parameters=[d newBufferWithLength:512 options:MTLResourceStorageModeShared];if(!gpuRoot||!rootReadback||!parameters)return 5;memset(parameters.contents,0xa5,parameters.length);uint32_t meta[4]={n,seed,trial,0};memcpy(parameters.contents,meta,sizeof meta);
        id<MTLIndirectCommandBuffer>icb=nil;
        if(cpu){MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=3;icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared];id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:0];[c setComputePipelineState:pipeline];[c setKernelBuffer:gpuRoot offset:64 atIndex:0];[c setKernelBuffer:gpu offset:64 atIndex:1];[c setKernelBuffer:parameters offset:0 atIndex:2];[c concurrentDispatchThreadgroups:MTLSizeMake((n+31)/32,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,1)error:&error]){emit(@{@"failure":@"preparation",@"error":error.description?:@""});return 8;}}
        id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];[blit copyFromBuffer:upload sourceOffset:0 toBuffer:gpu destinationOffset:0 size:bytes];[blit copyFromBuffer:root sourceOffset:0 toBuffer:gpuRoot destinationOffset:0 size:root.length];[blit endEncoding];
        if(dispatch){id<MTLComputeCommandEncoder>ce=[cb computeCommandEncoder];[ce setComputePipelineState:pipeline];[ce setBuffer:gpuRoot offset:64 atIndex:0];[ce setBuffer:gpu offset:64 atIndex:1];[ce setBuffer:parameters offset:0 atIndex:2];
            for(unsigned k=0;k<2;k++){[ce useResource:textures[k]usage:MTLResourceUsageRead];[ce useResource:parents[k]usage:MTLResourceUsageRead];[ce useResource:inputs[k]usage:MTLResourceUsageRead];}
            if(cpu){if(![scope adaptComputeEncoder:ce error:&error])return 8;@try{[ce executeCommandsInBuffer:icb withRange:NSMakeRange(0,1)];}@catch(NSException*x){[ce endEncoding];emit(@{@"failure":@"execution",@"error":x.reason?:@""});return 8;}}else[ce dispatchThreadgroups:MTLSizeMake((n+31)/32,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[ce endEncoding];}
        blit=[cb blitCommandEncoder];[blit copyFromBuffer:gpu sourceOffset:0 toBuffer:readback destinationOffset:0 size:bytes];[blit copyFromBuffer:gpuRoot sourceOffset:0 toBuffer:rootReadback destinationOffset:0 size:root.length];[blit endEncoding];[cb commit];[cb waitUntilCompleted];
        if(cb.status!=MTLCommandBufferStatusCompleted){emit(@{@"stage":@"completion",@"error":cb.error.description?:@"nil",@"command_status":@(cb.status)});return 6;}
        const uint32_t*actual=(const uint32_t*)((char*)readback.contents+64);unsigned bad=0,guards=0;for(unsigned i=0;i<bytes/4;i++)if(i<16||i>=16+n*4)guards+=((uint32_t*)readback.contents)[i]!=sentinel;
        for(unsigned i=0;i<n;i++){
            int x=int((i*3+trial)%12)-4,y=int((i*5+trial*2)%12)-4;x=si?((x%4+4)%4):MAX(0,MIN(3,x));y=si?((y%4+4)%4):MAX(0,MIN(3,y));
            uint32_t value=((i+8)*747796405u+seed)^0x12345678u^(bi?0x2468ace1u:0);uint32_t witness[4]={value^seed,i*3u,value*5u+trial,0xc0010000u^i^0x00040104u};
            for(unsigned c=0;c<4;c++){uint32_t expected=dispatch?uint32_t((x*47+y*29+c*37+(ti?91:13))&255)^witness[c]:sentinel;if(actual[i*4+c]!=expected)bad++;}
        }
        unsigned rootGuards=0;for(unsigned i=0;i<152;i++)rootGuards+=((unsigned char*)rootReadback.contents)[i]!=((unsigned char*)root.contents)[i];for(unsigned i=0;i<64;i++)rootGuards+=((unsigned char*)root.contents)[i]!=0xa5||((unsigned char*)root.contents)[88+i]!=0xa5;
        NSString*name=[NSString stringWithFormat:@"trial-%u",trial];[[NSData dataWithBytes:readback.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".output.bin"]]atomically:YES];
        [[NSData dataWithBytes:root.contents length:root.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".root.bin"]]atomically:YES];
        [[NSData dataWithBytes:rootReadback.contents length:rootReadback.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".private-root.bin"]]atomically:YES];
        [[NSData dataWithBytes:parameters.contents length:parameters.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".parameters.bin"]]atomically:YES];
        for(unsigned k=0;k<2;k++)[[NSData dataWithBytes:inputs[k].contents length:inputs[k].length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingFormat:@".input-%u.bin",k]]atomically:YES];
        [runs addObject:@{@"trial":@(trial),@"threads":@(n),@"seed":@(seed),@"texture":@(ti),@"sampler":@(si),@"input":@(bi),@"mismatches":@(bad),@"output_guard_mismatches":@(guards),@"root_guard_mismatches":@(rootGuards),@"command_status":@(cb.status),@"native_bytes_base64":[nativeBytes base64EncodedStringWithOptions:0],@"encoded_bytes_base64":[encoded base64EncodedStringWithOptions:0],@"texture_ID":@(bits(direct.image)),@"sampler_ID":@(bits(direct.sampling)),@"input_GPU_address_plus_offset":@(direct.input)}];
        ok&=!bad&&!guards&&!rootGuards;
    }
    if(scope)[scope restore];
    emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":identity,@"mode":mode,@"runs":runs,@"argument_layout":layout,@"status":ok?@"PASS":@"FAIL",@"user_dispatches":dispatch?@3:@0,@"native_shader":@YES,@"CPU_ICB":@(cpu),@"interposition":@(cpu),@"scope_events":scope.events?:@[],@"library_SHA256":sha([NSData dataWithContentsOfFile:@(argv[1])]),@"performance_benchmark":@NO});return ok?0:10;
}}
