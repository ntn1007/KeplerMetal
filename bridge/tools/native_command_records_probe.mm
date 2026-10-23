// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#include "KeplerCommandIR.h"
#include <cstdio>
#include <cstring>
#include <vector>
static void emit(id d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
    if(argc!=4)return 1;NSString*mode=@(argv[2]),*out=@(argv[3]);bool dispatch=[mode isEqual:@"execute"];
    if(!dispatch&&![mode isEqual:@"no_dispatch"])return 1;
    id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSDictionary*identity=KPKepler880MIdentity(d);if(!identity)return 2;
    NSError*error=nil;id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])]error:&error];
    id<MTLFunction>f=[lib newFunctionWithName:@"native_command_record_case"];if(!f)return 3;
    id<MTLComputePipelineState>p=[d newComputePipelineStateWithFunction:f error:&error];
    id<MTLArgumentEncoder>ae=[f newArgumentEncoderWithBufferIndex:0];
    if(!p||p.threadExecutionWidth!=32||p.maxTotalThreadsPerThreadgroup<32||ae.encodedLength!=40||ae.alignment!=8){emit(@{@"error":error.description?:@"native ABI differs",@"argument_bytes":@(ae.encodedLength)});return 3;}
    id<MTLCommandQueue>q=[d newCommandQueue];NSMutableArray*cases=[NSMutableArray new];
    const NSUInteger bytes=1792;std::vector<unsigned char>initial(bytes,0xa5);
    for(unsigned operation=0;operation<23;operation++){@autoreleasepool{
        id<MTLBuffer>records[2],download[2],context[2];
        for(unsigned k=0;k<2;k++){
            records[k]=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate];
            download[k]=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];
            KPCommandContext c={KP_COMMAND_CONTEXT_MAGIC,2,8,4,records[k].gpuAddress+256,128,3};
            if(k==0){if(operation==13)c.magic=0;if(operation==14)c.version=1;if(operation==15)c.capacity=9;
                if(operation==16)c.record_bytes=64;if(operation==18)c.pipeline_count=9;
                if(operation==19)c.max_bindings=3;if(operation==20)c.capacity=0;}
            context[k]=[d newBufferWithBytes:&c length:sizeof c options:MTLResourceStorageModeShared];
            if(!records[k]||!download[k]||!context[k]||!records[k].gpuAddress||records[k].gpuAddress+bytes>=(1ull<<40))return 4;
        }
        uint32_t data[128]={};id<MTLBuffer>storage=[d newBufferWithBytes:data length:sizeof data options:MTLResourceStorageModeShared];
        id<MTLBuffer>constants=[d newBufferWithBytes:data length:sizeof data options:MTLResourceStorageModeShared];
        uint64_t root[5]={context[0].gpuAddress,(uint64_t(KP_COMMAND_PIPELINE_MAGIC)<<32)|1,
            storage.gpuAddress+32,constants.gpuAddress+16,context[1].gpuAddress};
        id<MTLBuffer>args=[d newBufferWithBytes:root length:sizeof root options:MTLResourceStorageModeShared];
        id<MTLBuffer>upload=[d newBufferWithBytes:initial.data()length:bytes options:MTLResourceStorageModeShared];if(!args||!upload||!storage||!constants)return 4;
        NSData*contextBefore[2]={[NSData dataWithBytes:context[0].contents length:32],[NSData dataWithBytes:context[1].contents length:32]};
        id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];
        for(unsigned k=0;k<2;k++)[b copyFromBuffer:upload sourceOffset:0 toBuffer:records[k]destinationOffset:0 size:bytes];[b endEncoding];
        if(dispatch){id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:p];[e setBuffer:args offset:0 atIndex:0];[e setBytes:&operation length:4 atIndex:1];
            for(unsigned k=0;k<2;k++){[e useResource:records[k]usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e useResource:context[k]usage:MTLResourceUsageRead];}
            [e useResource:storage usage:MTLResourceUsageRead];[e useResource:constants usage:MTLResourceUsageRead];
            [e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];}
        b=[cb blitCommandEncoder];for(unsigned k=0;k<2;k++)[b copyFromBuffer:records[k]sourceOffset:0 toBuffer:download[k]destinationOffset:0 size:bytes];[b endEncoding];[cb commit];[cb waitUntilCompleted];
        if(cb.status!=MTLCommandBufferStatusCompleted){emit(@{@"error":cb.error.description?:@"command failed"});return 5;}
        bool intact=true;for(unsigned k=0;k<2;k++){intact&=!memcmp(contextBefore[k].bytes,context[k].contents,32);
            NSString*file=[NSString stringWithFormat:@"case-%u-records-%u.bin",operation,k];
            [[NSData dataWithBytes:download[k].contents length:bytes]writeToFile:[out stringByAppendingPathComponent:file]atomically:YES];}
        [cases addObject:@{@"operation":@(operation),@"command_status":@(cb.status),@"contexts_unchanged":@(intact),
            @"pipeline_token":@(root[1]),@"storage_address":@(root[2]),@"constant_address":@(root[3])}];if(!intact)return 6;
    }}
    emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":identity,@"mode":mode,@"cases":cases,
        @"producer_backend":@"native_msl",@"user_dispatches":dispatch?@23:@0,@"command_buffers":@23,
        @"record_execution":@NO,@"instruction_import":@NO,@"performance_benchmark":@NO});return 0;
}}
