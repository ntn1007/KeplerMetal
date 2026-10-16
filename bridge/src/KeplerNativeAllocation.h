// SPDX-License-Identifier: MIT
#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

// Explicit application API for ONE developer-qualified native compute profile.
// The JSON certificate and expected digest bind the immutable library, function,
// code hash/size, 58 native metadata words, driver and reserve4096 contract.
// This is an artifact pin, not a trusted-issuer signature or a general shader
// safety/compiler diagnosis. Qualify each profile on the target GPU first.
// Input bytes are copied. No file or external sidecar is opened by this API.
// The native GPU code is preserved; only metadata words9/11 may increase.
// Constructor access shares the CAS/import mutex and uses a thread-local scope.
// Other constructor interposition in the application must be serialized by it.
// Unsupported/cached/no-callback cases return nil. No installed driver or OCLP
// is changed. GPU dispatch/correctness/performance require separate tests.
extern "C" __attribute__((visibility("default")))
id<MTLComputePipelineState> KPCreateCertifiedNativeAllocationPipeline(
    id<MTLDevice> device,
    NSData *libraryData, NSString *expectedLibrarySHA256,
    NSData *certificateData, NSString *expectedCertificateSHA256,
    NSError **error, NSDictionary **evidence) NS_RETURNS_RETAINED;
