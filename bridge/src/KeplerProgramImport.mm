// SPDX-License-Identifier: MIT
// MRC facade: keep the historical retained-return C ABI, but share the CAS
// transport's mutex, callback context, driver gates and restoration checks.
// Link the complete runtime archive; this translation unit is not standalone.
#import "KeplerProgramImport.h"

extern "C" id<MTLComputePipelineState> KPInternalCASCreatePipeline(
    id<MTLDevice> device, NSURL *carrierLibrary, NSString *function,
    NSData *sm30Code, KeplerImportConfig config, NSError **error,
    NSDictionary **evidence) NS_RETURNS_RETAINED;
extern "C" id<MTLRenderPipelineState> KPInternalCASCreateRenderPipeline(
    id<MTLDevice> device, MTLRenderPipelineDescriptor *descriptor,
    NSData *fragmentSM30Code, KeplerImportConfig config, NSError **error,
    NSDictionary **evidence) NS_RETURNS_RETAINED;
extern "C" id<MTLRenderPipelineState> KPInternalCASCreateVertexPipeline(
    id<MTLDevice> device, MTLRenderPipelineDescriptor *descriptor,
    NSData *vertexSM30Code, KeplerImportConfig config, NSError **error,
    NSDictionary **evidence) NS_RETURNS_RETAINED;
extern "C" id<MTLRenderPipelineState> KPInternalCASCreateTessellationPipeline(
    id<MTLDevice> device, MTLRenderPipelineDescriptor *descriptor,
    NSData *evaluationCode, KeplerImportConfig config, NSError **error,
    NSDictionary **evidence) NS_RETURNS_RETAINED;
extern "C" id<MTLRenderPipelineState> KPInternalCASCreateGraphicsPipeline(
    id<MTLDevice> device, MTLRenderPipelineDescriptor *descriptor,
    NSData *vertexCode, KeplerImportConfig vertexConfig,
    NSData *fragmentCode, KeplerImportConfig fragmentConfig,
    NSError **error, NSDictionary **evidence) NS_RETURNS_RETAINED;
extern "C" id<MTLBuffer> KPInternalCASCreateHostBuffer(id<MTLDevice> device,
    const void *initialBytes, NSUInteger length, bool noCopy) NS_RETURNS_RETAINED;

extern "C" id<MTLComputePipelineState> KPCreatePipeline(
 id<MTLDevice>d,NSURL*l,NSString*f,NSData*c,KeplerImportConfig k,NSError**e,NSDictionary**v){
 return KPInternalCASCreatePipeline(d,l,f,c,k,e,v);
}
extern "C" id<MTLRenderPipelineState> KPCreateRenderPipeline(
 id<MTLDevice>d,MTLRenderPipelineDescriptor*p,NSData*c,KeplerImportConfig k,NSError**e,NSDictionary**v){
 return KPInternalCASCreateRenderPipeline(d,p,c,k,e,v);
}
extern "C" id<MTLRenderPipelineState> KPCreateVertexPipeline(
 id<MTLDevice>d,MTLRenderPipelineDescriptor*p,NSData*c,KeplerImportConfig k,NSError**e,NSDictionary**v){
 return KPInternalCASCreateVertexPipeline(d,p,c,k,e,v);
}
extern "C" id<MTLRenderPipelineState> KPCreateTessellationPipeline(
 id<MTLDevice>d,MTLRenderPipelineDescriptor*p,NSData*c,KeplerImportConfig k,NSError**e,NSDictionary**v){
 return KPInternalCASCreateTessellationPipeline(d,p,c,k,e,v);
}
extern "C" id<MTLRenderPipelineState> KPCreateGraphicsPipeline(
 id<MTLDevice>d,MTLRenderPipelineDescriptor*p,NSData*vc,KeplerImportConfig vk,
 NSData*fc,KeplerImportConfig fk,NSError**e,NSDictionary**v){
 return KPInternalCASCreateGraphicsPipeline(d,p,vc,vk,fc,fk,e,v);
}
extern "C" id<MTLBuffer> KPCreateHostBuffer(id<MTLDevice>d,const void*b,NSUInteger n,bool noCopy){
 return KPInternalCASCreateHostBuffer(d,b,n,noCopy);
}
