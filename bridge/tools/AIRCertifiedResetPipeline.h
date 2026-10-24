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
// Read-only own-PSO inspection on the qualified driver. Does not install an
// observer or replace code; saves a fresh CPU staging-code snapshot.
BOOL KPCheckCertifiedResetPipeline(id<MTLComputePipelineState>pipeline,
    NSString *certificatePath,NSString *codePath,NSDictionary **receipt,NSError **error);
#ifdef __cplusplus
}
#endif
