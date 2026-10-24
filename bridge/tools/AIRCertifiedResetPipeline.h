// SPDX-License-Identifier: MIT
#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
// Caller receives +1 ownership; implementation must be compiled with MRC.
#ifdef __cplusplus
extern "C" {
#endif
id<MTLComputePipelineState> KPNewCertifiedResetPipeline(id<MTLDevice>device,
    NSString *libraryPath,NSString *certificatePath,NSString *captureDirectory,
    NSDictionary **receipt,NSError **error) NS_RETURNS_RETAINED;
#ifdef __cplusplus
}
#endif
