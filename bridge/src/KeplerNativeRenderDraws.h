#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

NS_ASSUME_NONNULL_BEGIN
@class KPNativeRenderDrawBatch;
@interface KPRecordedNativeRenderDraw : NSObject
@property(nonatomic,readonly) NSData *commands;
@property(nonatomic,readonly) NSDictionary *evidence;
@end

// Laboratory transport: one pinned native pipeline, triangles, 64x48 RGBA32F,
// explicit scissor per record. This is not an implementation of the ICB API.
@interface KPNativeRenderDrawBatch : NSObject
@property(nonatomic,readonly) id<MTLRenderPipelineState> pipeline;
// Immutable, SHA-verified libraries plus a reflected stage-in ABI. These are
// registrations, not declarations of GPU qualification or a Metal family.
- (BOOL)registerVertexLibraryData:(NSData *)libraryData expectedSHA256:(NSString *)expected
                    manifestData:(NSData *)manifestData expectedManifestSHA256:(NSString *)manifestSHA
                           error:(NSError **)error;
- (nullable id<MTLRenderPipelineState>)pipelineForName:(NSString *)name;
- (nullable NSDictionary *)profileForPipeline:(id<MTLRenderPipelineState>)pipeline;
- (BOOL)acceptsRenderTarget:(id<MTLTexture>)target;
- (NSUInteger)maxVertexBindings;
- (NSUInteger)maxFragmentBindings;
// Encode resource references using the native encoder from this verified
// fragment function. Mutable parameter data stays separate from ABI bytes.
- (BOOL)encodeFragmentArgumentBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset
                       pipelineName:(NSString *)name bindingIndex:(NSUInteger)index
                          resources:(NSDictionary *)resources error:(NSError **)error;
// Sources are CPU-accessible tables encoded here. One source uses native blit;
// two use the SHA-qualified native selector kernel. The returned Private table
// is bound at offset256. Its counter is read at offset256 after completion.
// Consume in the producing command buffer or after successful completion.
// The client must not write the returned table. Arbitrary Private tables,
// cross-buffer pending dependencies and arbitrary GPU handles are unsupported.
- (nullable id<MTLBuffer>)newPrivateFragmentArgumentBufferForPipeline:(NSString *)name
                  bindingIndex:(NSUInteger)index sources:(NSArray<NSDictionary *> *)sources
                  selectedBank:(NSUInteger)bank commandBuffer:(id<MTLCommandBuffer>)commandBuffer
                  counter:(id<MTLBuffer> _Nullable * _Nullable)counter error:(NSError **)error;
- (BOOL)validateFragmentBindings:(NSDictionary *)bindings pipeline:(id<MTLRenderPipelineState>)pipeline error:(NSError **)error;
// Selector code is registered independently of vertex/fragment libraries.
// SHA-pinned native kernels and reflected interfaces; no GPU execution here.
- (BOOL)registerArgumentTableSelectorLibraryData:(NSData *)libraryData
                          expectedSHA256:(NSString *)expected error:(NSError **)error;
// Two certified native tables; the bank is read on GPU from a Private uint4
// at selectionOffset (16-byte aligned) and clamped to0/1 in the selector.
// No CPU choice/readback. The existing producer/completion rule still applies.
- (nullable id<MTLBuffer>)newPrivateFragmentArgumentBufferForPipeline:(NSString *)name
                  bindingIndex:(NSUInteger)index sources:(NSArray<NSDictionary *> *)sources
                  selectionBuffer:(id<MTLBuffer>)selection selectionOffset:(NSUInteger)selectionOffset
                  commandBuffer:(id<MTLCommandBuffer>)commandBuffer
                  counter:(id<MTLBuffer> _Nullable * _Nullable)counter error:(NSError **)error;
- (nullable KPRecordedNativeRenderDraw *)prepareFragmentDrawPipeline:(id<MTLRenderPipelineState>)pipeline
                        vertexBindings:(NSDictionary *)vertexBindings fragmentBindings:(NSDictionary *)fragmentBindings
                           vertexStart:(NSUInteger)start vertexCount:(NSUInteger)count
                             instances:(NSUInteger)instances baseInstance:(NSUInteger)base error:(NSError **)error;
- (BOOL)validateVertexBindings:(NSDictionary *)bindings pipeline:(id<MTLRenderPipelineState>)pipeline
                  vertexStart:(NSUInteger)start vertexCount:(NSUInteger)count
                    instances:(NSUInteger)instances baseInstance:(NSUInteger)base error:(NSError **)error;
- (nullable KPRecordedNativeRenderDraw *)prepareVertexDrawPipeline:(id<MTLRenderPipelineState>)pipeline
                     bindings:(NSDictionary *)bindings vertexStart:(NSUInteger)start vertexCount:(NSUInteger)count
                    instances:(NSUInteger)instances baseInstance:(NSUInteger)base error:(NSError **)error;
// Indexed stage-in profiles declare a post-baseVertex vertex fetch domain.
// As with native Metal, callers must supply indices in that domain. Private
// contents are not read or range-checked on the CPU before GPU submission.
- (BOOL)validateIndexedVertexBindings:(NSDictionary *)bindings pipeline:(id<MTLRenderPipelineState>)pipeline
                          indexCount:(NSUInteger)count indexBuffer:(id<MTLBuffer>)indices
                         indexOffset:(NSUInteger)offset kind:(NSUInteger)kind instances:(NSUInteger)instances
                          baseVertex:(NSInteger)vertexBase baseInstance:(NSUInteger)base error:(NSError **)error;
- (nullable KPRecordedNativeRenderDraw *)prepareIndexedVertexPipeline:(id<MTLRenderPipelineState>)pipeline
                            bindings:(NSDictionary *)bindings indexCount:(NSUInteger)count
                         indexBuffer:(id<MTLBuffer>)indices indexOffset:(NSUInteger)offset kind:(NSUInteger)kind
                           instances:(NSUInteger)instances baseVertex:(NSInteger)vertexBase
                        baseInstance:(NSUInteger)base error:(NSError **)error;
- (nullable KPRecordedNativeRenderDraw *)prepareIndexedFragmentPipeline:(id<MTLRenderPipelineState>)pipeline
                        vertexBindings:(NSDictionary *)vertexBindings fragmentBindings:(NSDictionary *)fragmentBindings
                             indexCount:(NSUInteger)count indexBuffer:(id<MTLBuffer>)indices
                            indexOffset:(NSUInteger)offset kind:(NSUInteger)kind instances:(NSUInteger)instances
                             baseVertex:(NSInteger)vertexBase baseInstance:(NSUInteger)base error:(NSError **)error;
- (nullable instancetype)initWithQueue:(id<MTLCommandQueue>)queue
                         libraryData:(NSData *)libraryData error:(NSError **)error;
// kind0: direct; kind1: UInt16 indexed; kind2: UInt32 indexed. Three vertices.
- (nullable KPRecordedNativeRenderDraw *)recordOnEncoder:(id<MTLRenderCommandEncoder>)encoder
                                                  kind:(NSUInteger)kind
                                           indexBuffer:(nullable id<MTLBuffer>)indices
                                                offset:(NSUInteger)offset
                                             instances:(NSUInteger)instances
                                               scissor:(MTLScissorRect)scissor
                                                 error:(NSError **)error;
// Creates/ends its own encoder; leaves the caller's command buffer uncommitted.
- (BOOL)encodeRecords:(NSArray<KPRecordedNativeRenderDraw *> *)records
              selected:(NSIndexSet *)selected
       toCommandBuffer:(id<MTLCommandBuffer>)commandBuffer
                target:(id<MTLTexture>)target
              evidence:(NSDictionary * _Nullable * _Nullable)evidence
                 error:(NSError **)error;
// Draw-only records for the public ICB adapter: encoder scissor/state is not
// embedded. Only this fixed native pipeline and bounded triangle profile.
- (nullable KPRecordedNativeRenderDraw *)prepareInheritedDrawKind:(NSUInteger)kind
                                                     indexBuffer:(nullable id<MTLBuffer>)indices
                                                          offset:(NSUInteger)offset
                                                       instances:(NSUInteger)instances
                                                           error:(NSError **)error;
- (BOOL)encodeInheritedRecords:(NSArray<KPRecordedNativeRenderDraw *> *)records
                      encoder:(id<MTLRenderCommandEncoder>)encoder
                       target:(id<MTLTexture>)target
                     evidence:(NSDictionary * _Nullable * _Nullable)evidence
                        error:(NSError **)error;
@end
NS_ASSUME_NONNULL_END
