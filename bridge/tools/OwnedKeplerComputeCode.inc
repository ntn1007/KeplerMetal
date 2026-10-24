// SPDX-License-Identifier: MIT
// Read-only profile already qualified by the native binding/readback probes.
#include <vector>
#include <algorithm>
static BOOL resetRegisteredObject(id object){
    if(!object||!captureRead((uintptr_t)object,8))return NO;
    Class cls=object_getClass(object);int n=objc_getClassList(nullptr,0);if(n<=0)return NO;
    std::vector<Class>classes(n);int count=objc_getClassList(classes.data(),n);
    return std::find(classes.begin(),classes.begin()+std::min(n,count),cls)!=classes.begin()+std::min(n,count);
}
static NSData *resetOwnedComputeCode(id<MTLComputePipelineState>pipeline){
    resetNeed([NSStringFromClass(object_getClass(pipeline))isEqual:@"NVMTLComputePipelineState"],"Native PSO class differs");
    Ivar slot=class_getInstanceVariable(object_getClass(pipeline),"_computePipeline");
    resetNeed(slot&&ivar_getOffset(slot)==72&&class_getInstanceSize(object_getClass(pipeline))>=80,"Native PSO layout differs");
    NSData*state=captureRead(captureWord(captureRead((uintptr_t)pipeline+72,8),0),32);
    resetNeed(state.length==32&&captureWord(state,8)==(uintptr_t)pipeline,"Native PSO back reference differs");
    id owner=(id)(uintptr_t)captureWord(state,16);
    resetNeed(resetRegisteredObject(owner)&&[NSStringFromClass(object_getClass(owner))isEqual:@"NVMTLFunctionVariant"],"Variant owner differs");
    slot=class_getInstanceVariable(object_getClass(owner),"_variant");
    resetNeed(slot&&ivar_getOffset(slot)==32&&class_getInstanceSize(object_getClass(owner))>=40,"Variant layout differs");
    NSData*data=captureRead(captureWord(captureRead((uintptr_t)owner+32,8),0),0x8b0);resetNeed(data.length==0x8b0,"Variant fields unreadable");
    uint64_t bytes=captureWord(data,24);uint32_t offset=0;memcpy(&offset,(const char*)data.bytes+36,4);
    resetNeed(bytes&&bytes<=65536&&bytes%64==0,"Native program bounds differ");
    id resource=(id)(uintptr_t)captureWord(data,0x898);
    resetNeed(resetRegisteredObject(resource)&&[resource conformsToProtocol:@protocol(MTLBuffer)],"Owned program resource differs");
    id<MTLBuffer>buffer=resource;
    resetNeed(buffer.device==pipeline.device&&offset<=buffer.length&&bytes<=buffer.length-offset&&buffer.gpuAddress+offset==captureWord(data,16),"Native program resource bounds differ");
    NSData*code=captureRead(captureWord(data,0x8a8),bytes);resetNeed(code.length==bytes,"Native CPU program unreadable");return code;
}
