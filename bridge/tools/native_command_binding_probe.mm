// SPDX-License-Identifier: MIT
// The suspect compute CB is NEVER committed. Optional submitted work is blit only.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerGPUIdentity.h"
#include "NativeCommandBoundaryCapture.inc"
#include <vector>
#include <algorithm>
#include <cstdio>
static void need(BOOL condition,NSString *message) {
    if(!condition)@throw[NSException exceptionWithName:@"BindingProbe" reason:message userInfo:nil];
}
static BOOL registeredObject(id object) {
    if(!object||!captureRead((uintptr_t)object,8))return NO;
    Class cls=object_getClass(object);int n=objc_getClassList(nullptr,0);
    if(n<=0)return NO;std::vector<Class>classes(n);int count=objc_getClassList(classes.data(),n);
    return std::find(classes.begin(),classes.begin()+std::min(n,count),cls)!=classes.begin()+std::min(n,count);
}
struct CodeState {
    id<MTLBuffer>buffer=nil;
    NSData *code=nil;
    uint64_t GPUAddress=0,offset=0,bytes=0;
    uint32_t registers=0;
};
static CodeState codeState(id<MTLComputePipelineState>pipeline) {
    need([NSStringFromClass(object_getClass(pipeline))isEqual:@"NVMTLComputePipelineState"],@"pipeline class");
    Ivar field=class_getInstanceVariable(object_getClass(pipeline),"_computePipeline");
    need(field&&ivar_getOffset(field)==72&&class_getInstanceSize(object_getClass(pipeline))>=80,@"pipeline layout");
    NSData *state=captureRead(captureWord(captureRead((uintptr_t)pipeline+72,8),0),32);
    need(state.length==32&&captureWord(state,8)==(uintptr_t)pipeline,@"pipeline owner back reference");
    id owner=(id)(uintptr_t)captureWord(state,16);
    need(registeredObject(owner)&&[NSStringFromClass(object_getClass(owner))isEqual:@"NVMTLFunctionVariant"],@"variant owner");
    field=class_getInstanceVariable(object_getClass(owner),"_variant");
    need(field&&ivar_getOffset(field)==32&&class_getInstanceSize(object_getClass(owner))>=40,@"variant layout");
    NSData *data=captureRead(captureWord(captureRead((uintptr_t)owner+32,8),0),0x8b0);
    need(data.length==0x8b0,@"variant fields readable");
    CodeState result;result.GPUAddress=captureWord(data,16);result.bytes=captureWord(data,24);
    uint32_t offset=0;memcpy(&offset,(const char*)data.bytes+36,4);result.offset=offset;
    memcpy(&result.registers,(const char*)data.bytes+48,4);
    result.code=captureRead(captureWord(data,0x8a8),result.bytes);
    id resource=(id)(uintptr_t)captureWord(data,0x898);
    need(registeredObject(resource)&&[resource conformsToProtocol:@protocol(MTLBuffer)],@"owned code buffer protocol");
    result.buffer=(id<MTLBuffer>)resource;
    need(result.bytes&&result.bytes<=65536&&result.code.length==result.bytes,@"bounded native program");
    need(result.offset<=result.buffer.length&&result.bytes<=result.buffer.length-result.offset,@"code buffer bounds");
    need(result.buffer.device==pipeline.device&&result.buffer.gpuAddress+result.offset==result.GPUAddress,@"code buffer identity/range");
    return result;
}
static NSDictionary *saveCPU(CodeState state,NSString *directory,NSString *label) {
    NSString *file=[label stringByAppendingString:@".cpu-code.bin"];
    need([state.code writeToFile:[directory stringByAppendingPathComponent:file]atomically:YES],@"CPU code save");
    return @{@"stage":label,@"file":file,@"SHA256":captureSHA(state.code),@"code_bytes":@(state.bytes),
        @"code_GPU_address":@(state.GPUAddress),@"code_buffer_GPU_address":@(state.buffer.gpuAddress),
        @"code_buffer_offset":@(state.offset),@"code_buffer_length":@(state.buffer.length),
        @"code_buffer_class":NSStringFromClass(object_getClass(state.buffer)),
        @"code_buffer_storage_mode":@(state.buffer.storageMode),@"registers":@(state.registers)};
}
// This helper cannot receive the suspect compute command buffer. It creates
// its own CB, opens only a blit encoder, and copies one owned validated range.
static NSDictionary *readCode(id<MTLDevice>device,id<MTLCommandQueue>queue,CodeState state,
                             NSString *directory,NSString *label,BOOL copy) {
    id<MTLBuffer>readback=[device newBufferWithLength:state.bytes+128 options:MTLResourceStorageModeShared];
    need(readback!=nil,@"readback allocation");memset(readback.contents,0xa5,readback.length);
    id<MTLCommandBuffer>blitCB=[queue commandBuffer];need(blitCB!=nil,@"blit CB");
    id<MTLBlitCommandEncoder>blit=[blitCB blitCommandEncoder];need(blit!=nil,@"blit encoder");
    if(copy)[blit copyFromBuffer:state.buffer sourceOffset:state.offset toBuffer:readback destinationOffset:64 size:state.bytes];
    [blit endEncoding];[blitCB commit];[blitCB waitUntilCompleted];
    need(blitCB.status==MTLCommandBufferStatusCompleted,@"blit completion");
    NSString *file=[label stringByAppendingString:@".resident-readback.bin"];
    NSData *data=[NSData dataWithBytes:readback.contents length:readback.length];
    need([data writeToFile:[directory stringByAppendingPathComponent:file]atomically:YES],@"resident readback save");
    return @{@"stage":label,@"file":file,@"SHA256":captureSHA(data),@"code_bytes":@(state.bytes),
        @"command_status":@(blitCB.status),@"committed_encoder":@"blit",@"copy_encoded":@(copy),@"compute_encoder_created":@NO};
}
struct Cursor {uintptr_t current=0,end=0,push=0;};
static Cursor cursor(id<MTLComputeCommandEncoder>encoder) {
    Ivar field=class_getInstanceVariable(object_getClass(encoder),"m_compute");
    need(field&&ivar_getOffset(field)==120&&class_getInstanceSize(object_getClass(encoder))==128,@"encoder layout");
    NSData *implementation=captureRead(captureWord(captureRead((uintptr_t)encoder+120,8),0),64);
    Cursor c;c.push=captureWord(implementation,32);NSData *data=captureRead(c.push,144);
    c.current=captureWord(data,0);c.end=captureWord(data,136);
    need(data.length==144&&c.current&&c.current<=c.end&&c.end-c.current<=1024*1024,@"encoder push bounds");return c;
}
static void emit(id object) {
    NSData *data=[NSJSONSerialization dataWithJSONObject:object options:NSJSONWritingPrettyPrinted error:nil];
    fwrite(data.bytes,1,data.length,stdout);puts("");
}
int main(int argc,char **argv) {@autoreleasepool {@try {
    need(argc==5,@"arguments");NSString *libraryPath=@(argv[1]),*name=@(argv[2]),*directory=@(argv[3]),*mode=@(argv[4]);
    need([@[@"inspect",@"encode",@"readback",@"readback_no_copy"]containsObject:mode],@"mode");
    BOOL readbackMode=[mode hasPrefix:@"readback"],copy=![mode isEqual:@"readback_no_copy"];
    id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(KPKepler880MIdentity(d)){need(!device,@"multiple GTX devices");device=d;}
    need(device!=nil,@"GTX identity");NSError *error=nil;
    id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:libraryPath]error:&error];need(library!=nil,error.description?:@"library");
    id<MTLFunction>function=[library newFunctionWithName:@"probe_boundary"];need(function!=nil,@"function");
    need(beginCapture(directory),@"constructor/profile capture gate");id<MTLComputePipelineState>pipeline=nil;NSDictionary *capture=nil;
    @try {pipeline=[device newComputePipelineStateWithFunction:function error:&error];}
    @finally {capture=finishCapture();}
    need(pipeline!=nil,error.description?:@"pipeline");
    NSMutableArray *snapshots=[NSMutableArray array],*readbacks=[NSMutableArray array];
    CodeState initial=codeState(pipeline);[snapshots addObject:saveCPU(initial,directory,@"constructed")];
    NSMutableDictionary *result=[@{@"case":name,@"mode":mode,@"device":device.name,@"registry_id":@(device.registryID),
        @"device_identity":KPKepler880MIdentity(device),@"capture":capture,@"CPU_snapshots":snapshots,@"readbacks":readbacks,
        @"suspect_compute_CB_committed":@NO,@"submitted_compute_dispatches":@0,@"encoded_compute_dispatches":@0,
        @"committed_blit_CBs":@0,@"core_runtime_linked":@NO,@"native_code_modified_by_probe":@NO,@"performance_benchmark":@NO}mutableCopy];
    if(![mode isEqual:@"inspect"]){
        id<MTLCommandQueue>queue=[device newCommandQueue];need(queue!=nil,@"queue");
        id<MTLCommandBuffer>shaderCB=[queue commandBuffer];need(shaderCB&&shaderCB.status==MTLCommandBufferStatusNotEnqueued,@"uncommitted compute CB");
        if(readbackMode)[readbacks addObject:readCode(device,queue,initial,directory,@"before-binding",copy)];
        need(shaderCB.status==MTLCommandBufferStatusNotEnqueued,@"compute CB unexpectedly enqueued");
        id<MTLComputeCommandEncoder>encoder=[shaderCB computeCommandEncoder];need(encoder!=nil,@"compute encoder");
        [encoder setComputePipelineState:pipeline];[snapshots addObject:saveCPU(codeState(pipeline),directory,@"pipeline-bound")];
        id<MTLBuffer>input=[device newBufferWithLength:1024 options:MTLResourceStorageModeShared];
        id<MTLBuffer>output=[device newBufferWithLength:1024 options:MTLResourceStorageModeShared];need(input&&output,@"ordinary bindings");
        memset(input.contents,0,input.length);memset(output.contents,0xa5,output.length);
        [encoder setBuffer:input offset:64 atIndex:0];[encoder setBuffer:output offset:64 atIndex:1];
        [snapshots addObject:saveCPU(codeState(pipeline),directory,@"buffers-bound")];Cursor before=cursor(encoder);
        [encoder dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];Cursor after=cursor(encoder);
        need(before.push==after.push&&after.current>before.current&&after.current<=before.end,@"command range");
        NSData *commands=captureRead(before.current,after.current-before.current);need(commands.length>0,@"command snapshot");
        need([commands writeToFile:[directory stringByAppendingPathComponent:@"uncommitted.commands.bin"]atomically:YES],@"command save");
        result[@"uncommitted_commands_SHA256"]=captureSHA(commands);result[@"uncommitted_commands_bytes"]=@(commands.length);
        [snapshots addObject:saveCPU(codeState(pipeline),directory,@"dispatch-encoded")];[encoder endEncoding];
        [snapshots addObject:saveCPU(codeState(pipeline),directory,@"encoding-ended")];
        need(shaderCB.status==MTLCommandBufferStatusNotEnqueued,@"compute CB unexpectedly submitted");
        if(readbackMode)[readbacks addObject:readCode(device,queue,codeState(pipeline),directory,@"after-encoding",copy)];
        need(shaderCB.status==MTLCommandBufferStatusNotEnqueued,@"compute CB submitted during readback");
        result[@"suspect_compute_CB_status"]=@(shaderCB.status);result[@"encoded_compute_dispatches"]=@1;result[@"committed_blit_CBs"]=@(readbacks.count);
        need([[NSData dataWithBytes:input.contents length:input.length]writeToFile:[directory stringByAppendingPathComponent:@"input.bin"]atomically:YES],@"input save");
        need([[NSData dataWithBytes:output.contents length:output.length]writeToFile:[directory stringByAppendingPathComponent:@"output.bin"]atomically:YES],@"output save");
    }
    result[@"status"]=@"OBSERVED";emit(result);return 0;
}@catch(NSException *exception){emit(@{@"status":@"FAILED",@"failure":exception.reason?:exception.name});return 10;}}}
