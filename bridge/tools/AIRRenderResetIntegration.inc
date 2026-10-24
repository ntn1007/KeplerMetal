// SPDX-License-Identifier: MIT
// ARC host hooks; compiled only with KP_AIR_RENDER_RESET=1.
#import "AIRCertifiedResetPipeline.h"
static id<MTLComputePipelineState>airResetPipeline;
static NSDictionary *airResetReceipt;
static bool airAppliesReset(NSString *mode){return [@[@"air_gpu",@"air_native",@"air_reference"]containsObject:mode];}
static bool airDispatchesReset(NSString *mode){return ![mode hasPrefix:@"air_no_reset"];}
static void airInitializeReset(id<MTLDevice>device,NSString *assets,NSString *directory,NSString *mode){
    NSString *variant=[mode isEqual:@"air_reference"]?@"reference":@"lowered";
    NSError *error=nil;NSDictionary *receipt=nil;
    airResetPipeline=KPNewCertifiedResetPipeline(device,
        [assets stringByAppendingPathComponent:[NSString stringWithFormat:@"reset-%@.metallib",variant]],
        [assets stringByAppendingPathComponent:[NSString stringWithFormat:@"reset-%@.certificate.json",variant]],
        [directory stringByAppendingPathComponent:@"reset-captures"],&receipt,&error);
    require(airResetPipeline!=nil,error.description.UTF8String?:"certified reset pipeline");airResetReceipt=receipt;
}
