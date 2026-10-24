#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

// Explicit process-local laboratory adapter, not a general driver installation.
// Supports registered CPU compute profiles, bounded uniform XYZ grids, native
// buffers/shared memory, and a separately qualified CPU render profile.
// General GPU-generated commands, gpuResourceID and unsupported selectors fail.
// Compute replay currently retains the native WAIT_FOR_IDLE after EVERY record.
// setBarrier/clearBarrier state is preserved through copy/reset and recorded in
// events, but clearing it does not enable concurrency in this serial transport.
@class KPGPUCommandSelection;
@interface KPCPUICBScope : NSObject
+ (instancetype)installOnDevice:(id<MTLDevice>)device
                         queue:(id<MTLCommandQueue>)queue
                      pipeline:(id<MTLComputePipelineState>)pipeline
                         error:(NSError **)error;
// Stronger identity path: scope creates and owns pipelines from this exact
// qualified metallib, checks native argument reflection and static memory.
+ (instancetype)installOnDevice:(id<MTLDevice>)device
                         queue:(id<MTLCommandQueue>)queue
                    libraryURL:(NSURL *)libraryURL
                expectedSHA256:(NSString *)expectedSHA256
                         error:(NSError **)error;
- (id<MTLComputePipelineState>)pipelineForFunction:(NSString *)function;
// Explicit registration for additional native libraries/functions with a
// SHA-pinned JSON ABI manifest. Registration is not GPU qualification.
// Schema1: three buffers and optional threadgroup(0). Schema2: reflected buffer
// layout and bounded uniform 1D/2D/3D geometry, subject to GPU qualification.
+ (instancetype)installOnDevice:(id<MTLDevice>)device
                         queue:(id<MTLCommandQueue>)queue
                    libraryURL:(NSURL *)libraryURL
                expectedSHA256:(NSString *)expectedSHA256
                   manifestURL:(NSURL *)manifestURL
        expectedManifestSHA256:(NSString *)manifestSHA256
                         error:(NSError **)error;
// Snapshot copies are taken before verification and passed directly to Metal;
// caller mutation/deletion of the source files cannot change the loaded bytes.
+ (instancetype)installOnDevice:(id<MTLDevice>)device
                         queue:(id<MTLCommandQueue>)queue
                   libraryData:(NSData *)libraryData
                expectedSHA256:(NSString *)expectedSHA256
                  manifestData:(NSData *)manifestData
        expectedManifestSHA256:(NSString *)manifestSHA256
                         error:(NSError **)error;
- (BOOL)adaptComputeEncoder:(id<MTLComputeCommandEncoder>)encoder error:(NSError **)error;
// Bounded GPU-timeline copy extension for native profiles owned by this scope.
// Manifest registrations support reflected buffer layouts and static shared.
// Dynamic shared argument0 uses a registered CPU-readable allocation bound;
// current command and retained-owner bounds are rechecked before encoding.
// Prepare occupied CPU compute slots before encoding the copy. Preparation uses
// native NOP/blit work and waits, but launches no user kernel. It is not a full
// ICB representation or GPU-generated command interface.
- (BOOL)prepareResidentComputeCommands:(id<MTLIndirectCommandBuffer>)buffer
                                 range:(NSRange)range error:(NSError **)error;
// Installs the public copyIndirectCommandBuffer selector on this encoder only.
// Bounded nonoverlapping occupied ranges, prepared profiles from the same pinned
// library/registration domain. Pipeline, geometry and native CB0 may differ.
// Active buffer ranges are revalidated against each manifest before use.
// Chained copies retain a flat union of resource owners, at most16 records.
// Consume in the same CB after the blit, or in a not-yet-enqueued retained CB
// after the copy CB has been committed on the same queue. Queue order carries
// that dependency; no CPU wait is performed. An uncommitted/enqueued-only/error
// predecessor or another queue is refused. Reset,
// rebind and CPU snapshot copy invalidate/preserve the shadow state explicitly;
// A resident execution range requires every occupied slot to be prepared;
// empty slots, GPU reset/optimize and concurrent encoders are outside this path.
- (BOOL)adaptBlitEncoder:(id<MTLBlitCommandEncoder>)encoder error:(NSError **)error;
// Trusted GPU selector over sealed, prepared native command templates.
// The library hash is pinned internally, not accepted solely from the caller.
- (BOOL)enableGPUCommandSelectionWithLibraryData:(NSData *)data
                               expectedSHA256:(NSString *)expected error:(NSError **)error;
// Additional pinned shader computes a bounded X-group count on GPU. Only the
// certified shared_mix library and its 1D prefix-safe kernels are admitted.
- (BOOL)enableGPUCommandGeometryWithLibraryData:(NSData *)data
                              expectedSHA256:(NSString *)expected error:(NSError **)error;
// Pinned GPU writer for validated output/counter bindings plus the grid prefix.
- (BOOL)enableGPUCommandBindingsWithLibraryData:(NSData *)data
                              expectedSHA256:(NSString *)expected error:(NSError **)error;
// Public-MSL command IR consumer over the same validated native registration.
// Reset/missing/unsupported records become zero-CTA launches. Uniform1D only;
// exact template local/shared state, no stage-in/stride/full concurrency yet.
- (BOOL)enableGPUCommandIRWithLibraryData:(NSData *)data
                         expectedSHA256:(NSString *)expected error:(NSError **)error;
- (KPGPUCommandSelection *)newGPUCommandIRFromBuffer:(id<MTLIndirectCommandBuffer>)source
                                       sourceRange:(NSRange)sourceRange
                                       destination:(id<MTLIndirectCommandBuffer>)destination
                                  destinationRange:(NSRange)destinationRange
                                         resources:(NSArray<NSDictionary *> *)resources
                                           records:(id<MTLBuffer>)records
                                      recordOffset:(NSUInteger)recordOffset
                                             error:(NSError **)error;
// Version2: contiguous reflected slots0..N-1 (N=3 or4), reflected constants slot.
// Uniform 1D/2D/3D; local/shared state stays identical to the native template.
// Each resources entry is {bindings:[{buffer,offset}, ...]} in slot order,
// omitting the constants slot. Inactive reflected slots retain catalogue entries.
// Exact same-buffer/same-offset sharing across different entries is permitted;
// complete duplicate entries, intra-entry alias and partial overlaps are refused.
- (BOOL)enableGPUCommandIRv2WithLibraryData:(NSData *)data
                           expectedSHA256:(NSString *)expected error:(NSError **)error;
- (KPGPUCommandSelection *)newGPUCommandIRv2FromBuffer:(id<MTLIndirectCommandBuffer>)source
                                         sourceRange:(NSRange)sourceRange
                                         destination:(id<MTLIndirectCommandBuffer>)destination
                                    destinationRange:(NSRange)destinationRange
                                           resources:(NSArray<NSDictionary *> *)resources
                                             records:(id<MTLBuffer>)records
                                        recordOffset:(NSUInteger)recordOffset
                                               error:(NSError **)error;
// Stable identities belong to this active scope's retained native pipelines,
// not candidate positions, process-independent IDs or Apple's gpuResourceID.
// They are never reused in this process; nil/foreign/restored scopes return0.
- (uint64_t)commandIRIdentityForPipeline:(id<MTLComputePipelineState>)pipeline
                                  error:(NSError **)error;
// Native source-lowered producers only. Allocate the extended context before
// exporting roots. GPU setters resolve stable pipeline IDs against each plan's
// immutable template/parameter/local-size catalogue; records stay ABI v2.
// Existing AIR/NAK producers must use the original v2 constructor instead.
- (KPGPUCommandSelection *)newGPUStableCommandIRFromBuffer:(id<MTLIndirectCommandBuffer>)source
                                             sourceRange:(NSRange)sourceRange
                                             destination:(id<MTLIndirectCommandBuffer>)destination
                                        destinationRange:(NSRange)destinationRange
                                               resources:(NSArray<NSDictionary *> *)resources
                                                 records:(id<MTLBuffer>)records
                                            recordOffset:(NSUInteger)recordOffset
                                                   error:(NSError **)error;
// Explicit reusable mode: one stable Private context per destination ICB,
// generation-tagged source root and producer/materializer/consumer leases.
// Reset only after every tracked CB completes. Uncommitted CBs must eventually
// be committed; no cancellation/recovery from Error is implemented. A fresh
// ICB is required after a poisoned submission. Single owner thread for encoding.
- (KPGPUCommandSelection *)newGPUReusableCommandIRFromBuffer:(id<MTLIndirectCommandBuffer>)source
                                               sourceRange:(NSRange)sourceRange
                                               destination:(id<MTLIndirectCommandBuffer>)destination
                                          destinationRange:(NSRange)destinationRange
                                                 resources:(NSArray<NSDictionary *> *)resources
                                                   records:(id<MTLBuffer>)records
                                              recordOffset:(NSUInteger)recordOffset
                                                     error:(NSError **)error;
// At most8 candidates and8 destinations, nonoverlapping, same registration.
// Cold initialization uses GPU blits and waits; it dispatches no user kernel.
// Input is Private uint[32] per destination. No CPU choice readback is needed.
- (KPGPUCommandSelection *)newGPUCommandSelectionFromBuffer:(id<MTLIndirectCommandBuffer>)source
                                             sourceRange:(NSRange)sourceRange
                                              destination:(id<MTLIndirectCommandBuffer>)destination
                                         destinationRange:(NSRange)destinationRange
                                                    input:(id<MTLBuffer>)input
                                              inputOffset:(NSUInteger)inputOffset
                                                    nonce:(uint32_t)nonce
                                                    error:(NSError **)error;
// Copies a sealed candidate and rewrites its X grid count to 1..original count
// (original count <=7). Local size, resources, pipeline and shared memory stay
// fixed. This does not support arbitrary shaders or general MSL ICB encoding.
- (KPGPUCommandSelection *)newGPUCommandGeometryFromBuffer:(id<MTLIndirectCommandBuffer>)source
                                             sourceRange:(NSRange)sourceRange
                                              destination:(id<MTLIndirectCommandBuffer>)destination
                                         destinationRange:(NSRange)destinationRange
                                                    input:(id<MTLBuffer>)input
                                              inputOffset:(NSUInteger)inputOffset
                                                    nonce:(uint32_t)nonce
                                                    error:(NSError **)error;
// Same certified kernels/grid contract as geometry. Each resource entry has
// output/counter MTLBuffers and outputOffset/counterOffset NSNumbers. At most4
// entries; Private buffers, disjoint, and sized for the largest original grid.
// The GPU chooses the entry and writes both addresses into a dedicated CB1.
- (KPGPUCommandSelection *)newGPUCommandBindingsFromBuffer:(id<MTLIndirectCommandBuffer>)source
                                             sourceRange:(NSRange)sourceRange
                                              destination:(id<MTLIndirectCommandBuffer>)destination
                                         destinationRange:(NSRange)destinationRange
                                                 resources:(NSArray<NSDictionary *> *)resources
                                                    input:(id<MTLBuffer>)input
                                              inputOffset:(NSUInteger)inputOffset
                                                    nonce:(uint32_t)nonce
                                                    error:(NSError **)error;
// Optional native CAS module. Each certificate is pinned by function name/SHA;
// the scope creates its MTLFunctions from the same immutable library bytes and
// requests corrected pipelines with native argument reflection. Unsupported
// certificates/module imports fail before device adaptation. Link with -ObjC.
+ (instancetype)installOnDevice:(id<MTLDevice>)device
                         queue:(id<MTLCommandQueue>)queue
                   libraryData:(NSData *)libraryData
                expectedSHA256:(NSString *)expectedSHA256
                  manifestData:(NSData *)manifestData
        expectedManifestSHA256:(NSString *)manifestSHA256
         nativeCASCertificates:(NSDictionary<NSString *,NSData *> *)certificates
     expectedCertificateSHA256:(NSDictionary<NSString *,NSString *> *)certificateHashes
                         error:(NSError **)error;
// Optional rendering transport must be linked into the client. One pinned
// vs_state/fs_state native library/PSO, triangles with3vertices, zero shader
// buffer bindings and one64x48RGBA32F target. No full render ICB contract.
+ (instancetype)installRenderingOnDevice:(id<MTLDevice>)device
                                  queue:(id<MTLCommandQueue>)queue
                            libraryData:(NSData *)libraryData
                         expectedSHA256:(NSString *)expectedSHA256
                                  error:(NSError **)error;
- (id<MTLRenderPipelineState>)renderPipeline;
// Additional reflected native stage-in pipelines. Supports direct triangles,
// Float4 attributes, per-vertex/per-instance buffers and reflected fragment
// argument buffers. Shared/Managed tables must be encoded by this scope.
- (BOOL)registerRenderVertexLibraryData:(NSData *)libraryData expectedSHA256:(NSString *)expected
                          manifestData:(NSData *)manifestData expectedManifestSHA256:(NSString *)manifestSHA
                                 error:(NSError **)error;
- (id<MTLRenderPipelineState>)renderPipelineForName:(NSString *)name;
- (BOOL)encodeFragmentArgumentBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset
                       pipelineName:(NSString *)name bindingIndex:(NSUInteger)index
                          resources:(NSDictionary *)resources error:(NSError **)error;
// Explicit extension for applications using this scope, not a driver upgrade.
// Immutable snapshots of certified source tables are copied/selected on GPU.
// The result and counter are Private; bind/readback respectively at offset256.
// Client writes to the result are forbidden by this cooperative contract.
// Consume in commandBuffer itself or after it completes successfully.
- (id<MTLBuffer>)newPrivateFragmentArgumentBufferForPipeline:(NSString *)name
                  bindingIndex:(NSUInteger)index sources:(NSArray<NSDictionary *> *)sources
                  selectedBank:(NSUInteger)bank commandBuffer:(id<MTLCommandBuffer>)commandBuffer
                  counter:(id<MTLBuffer> *)counter error:(NSError **)error;
- (BOOL)registerArgumentTableSelectorLibraryData:(NSData *)libraryData
                          expectedSHA256:(NSString *)expected error:(NSError **)error;
- (id<MTLBuffer>)newPrivateFragmentArgumentBufferForPipeline:(NSString *)name
                  bindingIndex:(NSUInteger)index sources:(NSArray<NSDictionary *> *)sources
                  selectionBuffer:(id<MTLBuffer>)selection selectionOffset:(NSUInteger)selectionOffset
                  commandBuffer:(id<MTLCommandBuffer>)commandBuffer
                  counter:(id<MTLBuffer> *)counter error:(NSError **)error;
// Add the optional qualified render domain to a registered compute scope.
// Descriptor commandTypes select compute/render independently; no mixed slots.
- (BOOL)registerRenderingLibraryData:(NSData *)libraryData
                     expectedSHA256:(NSString *)expectedSHA256
                              error:(NSError **)error;
// The scope observes the actual descriptor passed to the native constructor;
// supports only its controlled pass profile. Caller ends the returned encoder.
- (id<MTLRenderCommandEncoder>)renderEncoderWithDescriptor:(MTLRenderPassDescriptor *)descriptor
                                          commandBuffer:(id<MTLCommandBuffer>)commandBuffer
                                                  error:(NSError **)error;
- (void)restore;
// Returns a real native MTLFunction from an immutable library snapshot. Only
// its two root-encoder getters are adapted to our IRv2 ABI after validating
// native reflection. The installed native compiler is not replaced.
- (id<MTLFunction>)newCommandIRFunctionWithLibraryData:(NSData *)data
                                     expectedSHA256:(NSString *)expected
                                       functionName:(NSString *)name
                                    rootBufferIndex:(NSUInteger)index
                                              error:(NSError **)error;
// Source-lowered MSL variant: dense {context pointer, ulong token,3/4 pointers}
// with the complete reflected KPCommandContext layout. The caller explicitly
// opts into our wire ABI and supplies the exact library digest. This does not
// validate arbitrary shader semantics or confer Apple ICB/PSO resource IDs.
// Native pipeline factories remain native; getters return the existing owned
// resource encoder. Validate plan bindings before producer commit. Scope restore
// restores both function getters. Registered bytes are retained as a snapshot.
// Register a native source-lowered producer library once, then use ordinary
// device library constructors and library function factories. Only these named
// dense root0 functions are adapted; other functions stay native. No NAK program
// or carrier is required. The compiler/runtime must support the selected ABI.
- (BOOL)registerNativeSourceCommandIRLibraryData:(NSData *)data
                                expectedSHA256:(NSString *)expected
                                 functionNames:(NSArray<NSString *> *)names
                              reusableContexts:(BOOL)reusable
                                         error:(NSError **)error;
- (id<MTLFunction>)newNativeSourceCommandIRFunctionWithLibraryData:(NSData *)data
                                               expectedSHA256:(NSString *)expected
                                                 functionName:(NSString *)name
                                              rootBufferIndex:(NSUInteger)index
                                                        error:(NSError **)error;
// Same explicit source contract with an UInt64 generation-tagged context
// handle, not a native pointer/Apple resource ID. Compile the workspace header
// with KP_COMMAND_TAGGED_CONTEXT=1; other root constructors reject this schema.
- (id<MTLFunction>)newReusableCommandIRFunctionWithLibraryData:(NSData *)data
                                             expectedSHA256:(NSString *)expected
                                               functionName:(NSString *)name
                                            rootBufferIndex:(NSUInteger)index
                                                      error:(NSError **)error;
// Register a pinned, offline-compiled native-resource-ABI producer for this
// real function. The device's ordinary synchronous function factory then
// returns its native PSO. No general shader compilation/reflection extension.
- (BOOL)registerCommandIRProducerForFunction:(id<MTLFunction>)function
                                carrierData:(NSData *)carrier
                                programData:(NSData *)program
                                      error:(NSError **)error;
// Register an immutable source/carrier/program set once. Ordinary device
// library loads and native function factories then use the validated set.
- (BOOL)registerCommandIRLibraryData:(NSData *)data
                    expectedSHA256:(NSString *)expected
                       carrierData:(NSData *)carrier
                programsByFunction:(NSDictionary<NSString *, NSData *> *)programs
                             error:(NSError **)error;
@property(nonatomic,readonly) NSArray<NSDictionary *> *events;
@end

// Explicit application extension over validated native commands and resources.
@interface KPGPUCommandSelection : NSObject
@property(nonatomic,readonly) id<MTLBuffer> choices;
@property(nonatomic,readonly) id<MTLBuffer> invocationCounts;
// Private witnesses, readable after completion: geometry/bindings or IR status.
@property(nonatomic,readonly) id<MTLBuffer> generatedGeometry;
@property(nonatomic,readonly) NSArray<NSDictionary *> *events;
// IR plans only: opaque root for our AIR ABI, not an Apple argument-buffer ABI.
- (id<MTLBuffer>)newCommandIRArgumentsForCandidateIndex:(NSUInteger)candidate
                                        resourceIndex:(NSUInteger)resource error:(NSError **)error;
@property(nonatomic,readonly) NSArray<id<MTLBuffer>> *commandIRProducerResources;
// IRv2 supplies the public device argument-encoder factory for the bounded
// layout {ICB,pipeline,3/4 pointers}, using our AIR/IR ABI, not Apple's native
// ICB identity. Validate after bindings and before ANY producer commit.
// The target ICB owns its context. gpuResourceID remains unsupported.
- (BOOL)validateCommandIRArgumentBindings:(NSError **)error;
// Required BEFORE encoding any native producer for a reusable plan. The CB
// lease survives plan release and is closed only by terminal completion.
- (BOOL)reserveCommandIRProducerInCommandBuffer:(id<MTLCommandBuffer>)buffer
                                         error:(NSError **)error;
// Declare the indirect producer resources and retain its pipeline/root/push
// through completion. Producer must precede materialization on this same queue.
- (BOOL)encodeCommandIRInCommandBuffer:(id<MTLCommandBuffer>)buffer
                       afterProducer:(id<MTLCommandBuffer>)producer error:(NSError **)error;
- (BOOL)encodeProducerInCommandBuffer:(id<MTLCommandBuffer>)buffer error:(NSError **)error;
// Without a producer, initialized choice0 is used; this supports a causal
// control. Existing choices are always clamped to the sealed candidate range.
- (BOOL)encodeSelectionInCommandBuffer:(id<MTLCommandBuffer>)buffer error:(NSError **)error;
@end

// CPU snapshot copy; deliberately distinct from GPU-timeline blit copy.
BOOL KPCopyCPUICBCommands(id<MTLIndirectCommandBuffer>source,NSRange range,
                        id<MTLIndirectCommandBuffer>destination,NSUInteger index,
                        NSError **error);
