#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

// Experimental explicit application API. The certificate is an immutable,
// developer-approved AIR/SASS diagnosis for ONE named native kernel. Its SHA
// binds the original/replacement program, embedded AIR and metadata. It is not
// a signature from a trusted issuer or a proof of general kernel memory safety.
// Qualify the certificate on the GPU before using it in a real application.
// Inputs are copied before verification/loading. No path or external sidecar
// is opened by the API. Unsupported/cached/no-callback imports return nil.
// Pipeline construction is serialized inside this module. The application
// must serialize this call with other constructor interposition in its process.
// The native constructor IMP is replaced only during creation, then restored.
// No installed compiler/driver, other process, family flag or OCLP is modified.
// Returns a retained pipeline, including under ARC through this declaration.
extern "C" __attribute__((visibility("default")))
id<MTLComputePipelineState> KPCreateCertifiedNativeCASPipeline(
    id<MTLDevice> device,
    NSData *libraryData, NSString *expectedLibrarySHA256,
    NSData *certificateData, NSString *expectedCertificateSHA256,
    NSError **error, NSDictionary **evidence) NS_RETURNS_RETAINED;
