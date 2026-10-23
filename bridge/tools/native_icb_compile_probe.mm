// SPDX-License-Identifier: MIT
// Observe native factory/compiler refusals. No queue/encoder or interposition.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#import <objc/runtime.h>
#include <cstdio>
static void emit(id d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
    if(argc!=2)return 1;id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSDictionary*i=KPKepler880MIdentity(d);if(!i)return 2;
    NSError*error=nil;id<MTLLibrary>library=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])]error:&error];
    if(!library){emit(@{@"stage":@"library",@"error":error.description?:@"nil"});return 3;}
    id<MTLFunction>f=[library newFunctionWithName:@"reset_native_icb_slot"];if(!f)return 3;
    NSMutableDictionary*r=[@{@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":i,
        @"library_loaded":@YES,@"function_created":@YES,@"GPU_command_buffers":@0,@"GPU_dispatches":@0,
        @"interposition":@NO,@"scope":@"Native ICB kernel compilation and argument metadata only; never dispatch"}mutableCopy];
    @try{id<MTLArgumentEncoder>ae=[f newArgumentEncoderWithBufferIndex:0];r[@"function_encoder_created"]=@(ae!=nil);
        if(ae){r[@"encoder_class"]=NSStringFromClass(object_getClass(ae));r[@"encoded_length"]=@(ae.encodedLength);r[@"alignment"]=@(ae.alignment);}
    }@catch(NSException*e){r[@"argument_encoder_exception"]=e.reason?:e.name;}
    @try{MTLComputePipelineReflection*reflection=nil;
        id<MTLComputePipelineState>p=[d newComputePipelineStateWithFunction:f options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:&error];
        r[@"pipeline_created"]=@(p!=nil);r[@"pipeline_error"]=error.description?:@"";
        if(p){r[@"pipeline_class"]=NSStringFromClass(object_getClass(p));r[@"thread_width"]=@(p.threadExecutionWidth);r[@"max_threads"]=@(p.maxTotalThreadsPerThreadgroup);
            @try{MTLResourceID identity=p.gpuResourceID;r[@"pipeline_resource_ID"]=@(identity._impl);}
            @catch(NSException*e){r[@"pipeline_ID_exception"]=e.reason?:e.name;}
        }
        NSMutableArray*args=[NSMutableArray new];for(MTLArgument*a in reflection.arguments)if(a.type==MTLArgumentTypeBuffer){NSMutableArray*members=[NSMutableArray new];for(MTLStructMember*m in a.bufferStructType.members)[members addObject:@{@"name":m.name,@"offset":@(m.offset),@"type":@(m.dataType)}];[args addObject:@{@"index":@(a.index),@"data_size":@(a.bufferDataSize),@"members":members}];}r[@"reflection"]=args;
    }@catch(NSException*e){r[@"pipeline_created"]=@NO;r[@"pipeline_exception"]=e.reason?:e.name;}
    r[@"outcome"]=[r[@"pipeline_created"]boolValue]?@"PIPELINE_CREATED_NOT_EXECUTED":@"PIPELINE_REFUSED";emit(r);return 0;
}}
