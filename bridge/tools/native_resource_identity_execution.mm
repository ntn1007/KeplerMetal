// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#include <vector>
#include <cstring>
#include <cstdio>
struct DirectArguments{MTLResourceID image,sampling;uint64_t input;};
static_assert(sizeof(DirectArguments)==24,"Direct resource-argument ABI");
static void emit(id d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
static uint64_t bits(MTLResourceID value){uint64_t word;memcpy(&word,&value,8);return word;}
int main(int argc,char**argv){@autoreleasepool{
    if(argc!=4)return 1;NSString*mode=@(argv[2]),*out=@(argv[3]);
    BOOL native=[mode isEqual:@"native"],prepare=[mode isEqual:@"prepare"],dispatch=![mode isEqual:@"no_dispatch"]&&!prepare;
    if(!native&&dispatch&&![@[@"direct",@"wrong_texture",@"wrong_sampler",@"wrong_buffer"]containsObject:mode])return 1;
    id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSDictionary*identity=KPKepler880MIdentity(d);if(!identity)return 2;
    NSError*error=nil;id<MTLLibrary>library=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])]error:&error];
    if(!library){emit(@{@"stage":@"library",@"error":error.description?:@"nil"});return 3;}
    id<MTLFunction>function=[library newFunctionWithName:@"consume_native_resource_ids"];if(!function)return 3;
    MTLComputePipelineReflection*reflection=nil;
    id<MTLComputePipelineState>pipeline=[d newComputePipelineStateWithFunction:function options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:&error];
    if(!pipeline){emit(@{@"stage":@"pipeline",@"error":error.description?:@"nil"});return 3;}
    id<MTLArgumentEncoder>ae=[function newArgumentEncoderWithBufferIndex:0];
    NSMutableArray*layout=[NSMutableArray new];
    for(MTLArgument*a in reflection.arguments)if(a.type==MTLArgumentTypeBuffer&&a.index==0)
        for(MTLStructMember*m in a.bufferStructType.members)[layout addObject:@{@"name":m.name,@"offset":@(m.offset),@"type":@(m.dataType)}];
    if(ae.encodedLength!=24||ae.alignment!=8||layout.count!=3||[layout[0][@"offset"]unsignedIntegerValue]!=0||[layout[1][@"offset"]unsignedIntegerValue]!=8||[layout[2][@"offset"]unsignedIntegerValue]!=16||pipeline.threadExecutionWidth!=32||pipeline.maxTotalThreadsPerThreadgroup<32){emit(@{@"stage":@"ABI",@"layout":layout,@"encoded_length":@(ae.encodedLength),@"alignment":@(ae.alignment)});return 4;}
    if(prepare){emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":identity,@"mode":mode,@"status":@"PREPARED",@"argument_layout":layout,@"GPU_dispatches":@0,@"GPU_command_buffers":@0});return 0;}
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
    id<MTLCommandQueue>queue=[d newCommandQueue];NSMutableArray*runs=[NSMutableArray new];BOOL ok=YES;
    const uint32_t sentinel=0xd15ea5ed;const unsigned counts[3]={16,65,257};
    for(unsigned trial=0;trial<3;trial++){
        unsigned n=counts[trial],seed=0x125ab700u+trial*97u;NSUInteger bytes=(n+8)*16;
        id<MTLBuffer>inputs[2];std::vector<uint32_t>values(n+32);
        for(unsigned k=0;k<2;k++){for(unsigned i=0;i<values.size();i++)values[i]=(i*747796405u+seed)^0x12345678u^(k?0x2468ace1u:0);inputs[k]=[d newBufferWithBytes:values.data()length:values.size()*4 options:MTLResourceStorageModeShared];}
        id<MTLBuffer>root=[d newBufferWithLength:152 options:MTLResourceStorageModeShared];if(!root||!inputs[0]||!inputs[1])return 5;memset(root.contents,0xa5,root.length);
        unsigned ti=[mode isEqual:@"wrong_texture"]?1:0,si=[mode isEqual:@"wrong_sampler"]?1:0,bi=[mode isEqual:@"wrong_buffer"]?1:0;
        [ae setArgumentBuffer:root offset:64];[ae setTexture:textures[ti]atIndex:0];[ae setSamplerState:samplers[si]atIndex:1];[ae setBuffer:inputs[bi]offset:32 atIndex:2];
        NSData*nativeBytes=[NSData dataWithBytes:(char*)root.contents+64 length:24];
        DirectArguments direct={textures[ti].gpuResourceID,samplers[si].gpuResourceID,inputs[bi].gpuAddress+32};
        if(!native)memcpy((char*)root.contents+64,&direct,sizeof direct);
        NSData*encoded=[NSData dataWithBytes:(char*)root.contents+64 length:24];
        std::vector<uint32_t>initial(bytes/4,sentinel);id<MTLBuffer>upload=[d newBufferWithBytes:initial.data()length:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer>gpu=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate],readback=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];
        if(!inputs[0]||!inputs[1]||!root||!upload||!gpu||!readback)return 5;
        id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];[blit copyFromBuffer:upload sourceOffset:0 toBuffer:gpu destinationOffset:0 size:bytes];[blit endEncoding];
        if(dispatch){id<MTLComputeCommandEncoder>ce=[cb computeCommandEncoder];[ce setComputePipelineState:pipeline];[ce setBuffer:root offset:64 atIndex:0];[ce setBuffer:gpu offset:64 atIndex:1];uint32_t meta[4]={n,seed,trial,0};[ce setBytes:meta length:sizeof meta atIndex:2];
            for(unsigned k=0;k<2;k++){[ce useResource:textures[k]usage:MTLResourceUsageRead];[ce useResource:parents[k]usage:MTLResourceUsageRead];[ce useResource:inputs[k]usage:MTLResourceUsageRead];}
            [ce dispatchThreadgroups:MTLSizeMake((n+31)/32,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[ce endEncoding];}
        blit=[cb blitCommandEncoder];[blit copyFromBuffer:gpu sourceOffset:0 toBuffer:readback destinationOffset:0 size:bytes];[blit endEncoding];[cb commit];[cb waitUntilCompleted];
        if(cb.status!=MTLCommandBufferStatusCompleted){emit(@{@"stage":@"completion",@"error":cb.error.description?:@"nil",@"command_status":@(cb.status)});return 6;}
        const uint32_t*actual=(const uint32_t*)((char*)readback.contents+64);unsigned bad=0,guards=0;for(unsigned i=0;i<16;i++)guards+=((uint32_t*)readback.contents)[i]!=sentinel||((uint32_t*)readback.contents)[16+n*4+i]!=sentinel;
        for(unsigned i=0;i<n;i++){
            int x=int((i*3+trial)%12)-4,y=int((i*5+trial*2)%12)-4;x=si?((x%4+4)%4):MAX(0,MIN(3,x));y=si?((y%4+4)%4):MAX(0,MIN(3,y));
            uint32_t value=((i+8)*747796405u+seed)^0x12345678u^(bi?0x2468ace1u:0);uint32_t witness[4]={value^seed,i*3u,value*5u+trial,0xc0010000u^i^0x00040104u};
            for(unsigned c=0;c<4;c++){uint32_t expected=dispatch?uint32_t((x*47+y*29+c*37+(ti?91:13))&255)^witness[c]:sentinel;if(actual[i*4+c]!=expected)bad++;}
        }
        unsigned rootGuards=0;for(unsigned i=0;i<64;i++)rootGuards+=((unsigned char*)root.contents)[i]!=0xa5||((unsigned char*)root.contents)[88+i]!=0xa5;
        NSString*name=[NSString stringWithFormat:@"trial-%u",trial];[[NSData dataWithBytes:readback.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".output.bin"]]atomically:YES];
        [[NSData dataWithBytes:root.contents length:root.length]writeToFile:[out stringByAppendingPathComponent:[name stringByAppendingString:@".root.bin"]]atomically:YES];
        [runs addObject:@{@"trial":@(trial),@"threads":@(n),@"seed":@(seed),@"texture":@(ti),@"sampler":@(si),@"input":@(bi),@"mismatches":@(bad),@"output_guard_mismatches":@(guards),@"root_guard_mismatches":@(rootGuards),@"command_status":@(cb.status),@"native_bytes_base64":[nativeBytes base64EncodedStringWithOptions:0],@"encoded_bytes_base64":[encoded base64EncodedStringWithOptions:0],@"texture_ID":@(bits(direct.image)),@"sampler_ID":@(bits(direct.sampling)),@"input_GPU_address_plus_offset":@(direct.input)}];
        ok&=!bad&&!guards&&!rootGuards;
    }
    emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":identity,@"mode":mode,@"runs":runs,@"argument_layout":layout,@"status":ok?@"PASS":@"FAIL",@"user_dispatches":dispatch?@3:@0,@"native_shader":@YES,@"interposition":@NO,@"performance_benchmark":@NO});return ok?0:10;
}}
