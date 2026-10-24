// SPDX-License-Identifier: MIT
// Construction only: no queue, allocation, encoder or GPU dispatch.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#include <cstdio>
#ifndef KP_COMMAND_CAPTURE
#define KP_COMMAND_CAPTURE 0
#endif
#if KP_COMMAND_CAPTURE
#include "NativeCommandBoundaryCapture.inc"
#endif
static void emit(id value) {
    NSData *data=[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];
    fwrite(data.bytes,1,data.length,stdout);puts("");
}
int main(int argc,char **argv) {@autoreleasepool {
    if(argc!=(KP_COMMAND_CAPTURE?4:3))return 1;
    id<MTLDevice>device=nil;
    for(id<MTLDevice>d in MTLCopyAllDevices())if(KPKepler880MIdentity(d)) {
        if(device)return 2;device=d;
    }
    if(!device)return 2;
    NSMutableDictionary *result=[@{@"case":@(argv[2]),@"device":device.name,
        @"registry_id":@(device.registryID),@"device_identity":KPKepler880MIdentity(device),
        @"GPU_command_buffers":@0,@"GPU_dispatches":@0,@"GPU_resources_allocated":@0,
        @"runtime_linked":@NO,@"interposition":@(KP_COMMAND_CAPTURE!=0),
        @"resource_accounting_scope":@"explicit application calls, not internal driver allocations"}mutableCopy];
    @try {
        NSError *error=nil;
        id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])]error:&error];
        result[@"library_loaded"]=@(library!=nil);
        if(!library){result[@"library_error"]=error.description?:@"";emit(result);return 3;}
        id<MTLFunction>function=[library newFunctionWithName:@"probe_boundary"];
        result[@"function_created"]=@(function!=nil);
        if(!function){emit(result);return 4;}
        @try {
            id<MTLArgumentEncoder>encoder=[function newArgumentEncoderWithBufferIndex:0];
            result[@"encoder_created"]=@(encoder!=nil);
            if(encoder){result[@"encoder_length"]=@(encoder.encodedLength);result[@"encoder_alignment"]=@(encoder.alignment);}
        }@catch(NSException *exception){result[@"encoder_exception"]=exception.reason?:exception.name;}
        MTLComputePipelineReflection *reflection=nil;error=nil;
        id<MTLComputePipelineState>pipeline=nil;
#if KP_COMMAND_CAPTURE
        if(!beginCapture(@(argv[3]))){emit(@{@"failure":@"capture_profile_refused"});return 5;}
#endif
        @try{pipeline=[device newComputePipelineStateWithFunction:function
            options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:&error];}
        @finally{
#if KP_COMMAND_CAPTURE
            result[@"capture"]=finishCapture();
#endif
        }
        result[@"pipeline_created"]=@(pipeline!=nil);
        result[@"pipeline_error"]=error.description?:@"";
        if(error){result[@"error_domain"]=error.domain;result[@"error_code"]=@(error.code);}
        NSMutableArray *arguments=[NSMutableArray new];
        for(MTLArgument *a in reflection.arguments) {
            NSMutableDictionary *item=[@{@"index":@(a.index),@"type":@(a.type),@"active":@(a.active)}mutableCopy];
            if(a.type==MTLArgumentTypeBuffer){item[@"data_type"]=@(a.bufferDataType);item[@"data_size"]=@(a.bufferDataSize);item[@"alignment"]=@(a.bufferAlignment);}
            [arguments addObject:item];
        }
        result[@"reflection"]=arguments;
        if(pipeline){result[@"thread_width"]=@(pipeline.threadExecutionWidth);result[@"max_threads"]=@(pipeline.maxTotalThreadsPerThreadgroup);}
        result[@"outcome"]=pipeline?@"PIPELINE_CREATED_NOT_EXECUTED":@"PIPELINE_REFUSED";
    }@catch(NSException *exception){result[@"exception"]=exception.reason?:exception.name;result[@"outcome"]=@"EXCEPTION";}
    emit(result);return 0;
}}
