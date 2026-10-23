// SPDX-License-Identifier: MIT
// Public native argument encoders only. No interposition or GPU submission.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import "KeplerGPUIdentity.h"
#include <cstring>
#include <cstdio>
#include <dlfcn.h>

static NSDictionary*methodInfo(id object,SEL selector){
    Method m=class_getInstanceMethod(object_getClass(object),selector);
    if(!m)return @{@"present":@NO};
    Dl_info info={};dladdr((const void*)method_getImplementation(m),&info);
    return @{@"present":@YES,@"encoding":@(method_getTypeEncoding(m)),@"image":info.dli_fname?@(info.dli_fname):@""};
}
static NSDictionary*resourceID(id object){
    NSMutableDictionary*r=[@{@"class":NSStringFromClass(object_getClass(object)),@"method":methodInfo(object,@selector(gpuResourceID))}mutableCopy];
    @try{
        MTLResourceID value=[(id<MTLTexture>)object gpuResourceID];
        static_assert(sizeof(value)==sizeof(uint64_t),"Resource ID ABI");uint64_t word=0;memcpy(&word,&value,sizeof word);
        r[@"returned"]=@YES;r[@"word"]=@(word);
    }@catch(NSException*e){r[@"returned"]=@NO;r[@"exception"]=e.reason?:e.name;}
    return r;
}
static void emit(id d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(){@autoreleasepool{
    id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSDictionary*identity=KPKepler880MIdentity(d);if(!identity)return 2;
    id<MTLBuffer>buffer=[d newBufferWithLength:256 options:MTLResourceStorageModeShared];
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:4 height:4 mipmapped:NO];
    td.storageMode=MTLStorageModeManaged;td.usage=MTLTextureUsageShaderRead;
    id<MTLTexture>texture=[d newTextureWithDescriptor:td];
    MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];sd.supportArgumentBuffers=YES;
    id<MTLSamplerState>sampler=[d newSamplerStateWithDescriptor:sd];if(!buffer||!texture||!sampler)return 3;
    NSMutableArray*rows=[NSMutableArray new];BOOL pointerOK=NO;
    for(NSString*kind in @[@"pointer",@"texture",@"sampler",@"ICB",@"pipeline"]){
        NSMutableDictionary*r=[@{@"kind":kind}mutableCopy];
        @try{
            MTLArgumentDescriptor*a=[MTLArgumentDescriptor argumentDescriptor];a.index=0;a.arrayLength=1;a.access=MTLArgumentAccessReadOnly;
            a.dataType=[kind isEqual:@"pointer"]?MTLDataTypePointer:[kind isEqual:@"texture"]?MTLDataTypeTexture:[kind isEqual:@"sampler"]?MTLDataTypeSampler:[kind isEqual:@"ICB"]?MTLDataTypeIndirectCommandBuffer:MTLDataTypeComputePipeline;
            a.textureType=MTLTextureType2D;
            id<MTLArgumentEncoder>encoder=[d newArgumentEncoderWithArguments:@[a]];
            r[@"encoder_created"]=@(encoder!=nil);
            if(encoder){
                r[@"encoder_class"]=NSStringFromClass(object_getClass(encoder));r[@"encoded_length"]=@(encoder.encodedLength);r[@"alignment"]=@(encoder.alignment);
                r[@"ICB_setter"]=methodInfo(encoder,@selector(setIndirectCommandBuffer:atIndex:));
                if(encoder.encodedLength&&encoder.encodedLength<=1024){
                    id<MTLBuffer>root=[d newBufferWithLength:encoder.encodedLength+128 options:MTLResourceStorageModeShared];
                    memset(root.contents,0xa5,root.length);[encoder setArgumentBuffer:root offset:64];
                    if([kind isEqual:@"pointer"])[encoder setBuffer:buffer offset:32 atIndex:0];
                    else if([kind isEqual:@"texture"])[encoder setTexture:texture atIndex:0];
                    else if([kind isEqual:@"sampler"])[encoder setSamplerState:sampler atIndex:0];
                    else if([kind isEqual:@"ICB"])[encoder setIndirectCommandBuffer:nil atIndex:0];
                    else [encoder setComputePipelineState:nil atIndex:0];
                    uint64_t word=0;memcpy(&word,(char*)root.contents+64,MIN(sizeof word,encoder.encodedLength));r[@"encoded_word"]=@(word);
                    BOOL guards=YES;for(NSUInteger i=0;i<64;i++)guards&=((unsigned char*)root.contents)[i]==0xa5&&((unsigned char*)root.contents)[64+encoder.encodedLength+i]==0xa5;
                    r[@"guards_intact"]=@(guards);r[@"encoded"]=@YES;
                    if([kind isEqual:@"pointer"]){pointerOK=guards&&encoder.encodedLength==8&&word==buffer.gpuAddress+32;r[@"pointer_matches_GPU_address_plus_offset"]=@(pointerOK);}
                }
            }
        }@catch(NSException*e){r[@"exception"]=e.reason?:e.name;}
        [rows addObject:r];
    }
    NSMutableArray*factories=[NSMutableArray new];
    for(NSNumber*render in @[@NO,@YES]){
        NSMutableDictionary*r=[@{@"render":render}mutableCopy];
        @try{MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=render.boolValue?MTLIndirectCommandTypeDraw:MTLIndirectCommandTypeConcurrentDispatch;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;
            id<MTLIndirectCommandBuffer>b=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared];r[@"created"]=@(b!=nil);if(b)r[@"resource_ID"]=resourceID(b);
        }@catch(NSException*e){r[@"exception"]=e.reason?:e.name;}[factories addObject:r];
    }
    emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":identity,@"rows":rows,@"ICB_factories":factories,
        @"native_texture_ID":resourceID(texture),@"native_sampler_ID":resourceID(sampler),
        @"pointer_control_passed":@(pointerOK),@"GPU_command_buffers":@0,@"GPU_dispatches":@0,
        @"scope":@"Observed native public binding/identity behavior; no shader execution, replacement selector or compatibility claim"});
    return pointerOK?0:10;
}}
