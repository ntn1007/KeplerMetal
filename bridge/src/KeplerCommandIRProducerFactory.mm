// SPDX-License-Identifier: MIT
#import "KeplerProgramImport.h"
#import <objc/runtime.h>
// The MRC transport returns a retained native pipeline; ownership is explicit.
extern "C" id<MTLComputePipelineState> KPInternalCreateApprovedSM30Pipeline(
    id<MTLDevice>, NSData *, NSString *, NSData *, KeplerImportConfig,
    NSError **, NSDictionary **) NS_RETURNS_RETAINED;
extern "C" id<MTLComputePipelineState> KPInternalCreateApprovedSM30PipelineWithDescriptor(
    id<MTLDevice>, NSData *, NSString *, NSData *, KeplerImportConfig,
    MTLComputePipelineDescriptor *, NSError **, NSDictionary **) NS_RETURNS_RETAINED;

@interface KPCommandIRProducerFactory : NSObject
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
    carrier:(NSData *)carrier program:(NSData *)program error:(NSError **)error
    evidence:(NSDictionary **)evidence NS_RETURNS_RETAINED;
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
    carrier:(NSData *)carrier program:(NSData *)program descriptor:(MTLComputePipelineDescriptor *)descriptor
    error:(NSError **)error evidence:(NSDictionary **)evidence NS_RETURNS_RETAINED;
@end
@implementation KPCommandIRProducerFactory
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
    carrier:(NSData *)carrier program:(NSData *)program error:(NSError **)error
    evidence:(NSDictionary **)evidence {
    NSDictionary*proof=nil;id<MTLComputePipelineState>pipeline=KPInternalCreateApprovedSM30Pipeline(device, carrier,
        @"command_ir_native_root_carrier", program, {24,576,576}, error, &proof);
    if(pipeline)objc_setAssociatedObject(pipeline,sel_registerName("KeplerMetalProducerEvidence-v1"),proof,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    if(evidence)*evidence=proof;return pipeline;
}
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
    carrier:(NSData *)carrier program:(NSData *)program descriptor:(MTLComputePipelineDescriptor *)descriptor
    error:(NSError **)error evidence:(NSDictionary **)evidence {
    NSDictionary*proof=nil;id<MTLComputePipelineState>pipeline=KPInternalCreateApprovedSM30PipelineWithDescriptor(device,carrier,
        @"command_ir_native_root_carrier",program,{24,576,576},descriptor,error,&proof);
    if(pipeline)objc_setAssociatedObject(pipeline,sel_registerName("KeplerMetalProducerEvidence-v1"),proof,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    if(evidence)*evidence=proof;return pipeline;
}
@end
