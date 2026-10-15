// SPDX-License-Identifier: MIT
#import "KeplerProgramImport.h"
// The MRC transport returns a retained native pipeline; ownership is explicit.
extern "C" id<MTLComputePipelineState> KPInternalCreateApprovedSM30Pipeline(
    id<MTLDevice>, NSData *, NSString *, NSData *, KeplerImportConfig,
    NSError **, NSDictionary **) NS_RETURNS_RETAINED;

@interface KPCommandIRProducerFactory : NSObject
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
    carrier:(NSData *)carrier program:(NSData *)program error:(NSError **)error
    evidence:(NSDictionary **)evidence NS_RETURNS_RETAINED;
@end
@implementation KPCommandIRProducerFactory
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
    carrier:(NSData *)carrier program:(NSData *)program error:(NSError **)error
    evidence:(NSDictionary **)evidence {
    return KPInternalCreateApprovedSM30Pipeline(device, carrier,
        @"command_ir_native_root_carrier", program, {24,576,576}, error, evidence);
}
@end
