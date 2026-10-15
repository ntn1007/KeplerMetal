// Experimental application-local program import. The installed driver owns GPU state.
#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>

struct KeplerImportConfig {
    uint32_t registers;
    uint32_t launch_word_9;
    uint32_t launch_word_11;
};
// Experimental local-memory allocation contract for the pinned native reference
// library. Byte capacities are observed carrier metadata, not a GPU limit.
// Native local allocations are preserved; instruction count/GPR are updated
// and the previously qualified structured-control word11=576 is requested.
// The caller must supply truthful compiled-code scratch requirements and match
// the carrier's buffer, barrier and static-memory ABI. This is not a verifier
// for arbitrary machine code or a new MSL frontend.
struct KeplerLocalMemoryConfig {
    uint32_t registers;
    uint32_t required_scratch_bytes;
    uint32_t carrier_local_bytes;
    uint32_t carrier_spill_bytes;
    uint32_t carrier_control_barriers;
};
extern "C" id<MTLComputePipelineState> KPCreateLocalMemoryPipeline(
    id<MTLDevice> device, NSData *carrierLibrary, NSString *function,
    NSData *sm30Code, KeplerLocalMemoryConfig config, NSError **error,
    NSDictionary **evidence) NS_RETURNS_RETAINED;
// Returns a retained pipeline. The caller releases it (manual Objective-C ownership).
// Accepts observed NVIDIA container versions 7/8/9 with validated sections.
// Pins the installed GeForceMTLDriver SHA256 and observed _variant ABI. Every
// matching constructor call must pass; cached/no-callback imports are rejected.
// KP imports are serialized; the host must not replace the constructor itself.
// Evidence concerns constructor bytes and decoded size/GPR. Prove GPU execution
// separately by dispatch/readback checks against CPU and distinct native control.
// Carrier and code must have matched resource/static-memory ABIs; this API does
// not infer kernel memory safety or implement a general MSL frontend.
extern "C" id<MTLComputePipelineState> KPCreatePipeline(
    id<MTLDevice> device, NSURL *carrierLibrary, NSString *function,
    NSData *sm30Code, KeplerImportConfig config, NSError **error,
    NSDictionary **evidence) NS_RETURNS_RETAINED;
// Fragment-only import; the original 80-byte graphics header and vertex stage
// are preserved. Qualified scopes are recorded in results/hardware-coverage.json.
extern "C" id<MTLRenderPipelineState> KPCreateRenderPipeline(
    id<MTLDevice> device, MTLRenderPipelineDescriptor *descriptor,
    NSData *fragmentSM30Code, KeplerImportConfig config, NSError **error,
    NSDictionary **evidence) NS_RETURNS_RETAINED;
extern "C" id<MTLRenderPipelineState> KPCreateVertexPipeline(
    id<MTLDevice> device, MTLRenderPipelineDescriptor *descriptor,
    NSData *vertexSM30Code, KeplerImportConfig config, NSError **error,
    NSDictionary **evidence) NS_RETURNS_RETAINED;
// Post-tessellation stage2 import; native tessellator/header/fragment preserved.
extern "C" id<MTLRenderPipelineState> KPCreateTessellationPipeline(
    id<MTLDevice> device, MTLRenderPipelineDescriptor *descriptor,
    NSData *evaluationCode, KeplerImportConfig config, NSError **error,
    NSDictionary **evidence) NS_RETURNS_RETAINED;
extern "C" id<MTLRenderPipelineState> KPCreateGraphicsPipeline(
    id<MTLDevice> device, MTLRenderPipelineDescriptor *descriptor,
    NSData *vertexCode, KeplerImportConfig vertexConfig,
    NSData *fragmentCode, KeplerImportConfig fragmentConfig,
    NSError **error, NSDictionary **evidence) NS_RETURNS_RETAINED;
// Retained CPU-visible staging buffer. noCopy wraps page-aligned malloc memory.
extern "C" id<MTLBuffer> KPCreateHostBuffer(id<MTLDevice> device,
    const void *initialBytes, NSUInteger length, bool noCopy) NS_RETURNS_RETAINED;
