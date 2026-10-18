// SPDX-License-Identifier: MIT
#import "KeplerCPUICB.h"
#import "KeplerNativeCommands.h"

// Optional explicit SDK extension. This does not change MTLDevice capabilities
// or implement Apple's ordinary concurrent encoder. Only the pinned native
// observe_a/b library, one group of one thread and 1..4 entries are admitted.
// This profile communicates atomically through sync[0..2], writes out[0..7]
// and reads four uint32 config words. Other shader footprints are refused.
@interface KPResidentBatch : NSObject
// Snapshots the selected owned SDK slots and their records, not the mutable ICB.
// Preparation may submit the existing NOP/copy work, but launches no user kernel.
// barrierBefore adds boundaries at positions in indices (not ICB slot numbers).
// Existing source-slot setBarrier requests are also snapshotted and honored.
// Later clearBarrier/reset calls do not mutate the prepared snapshot. A boundary
// drains ALL earlier launches before the next position; the final wait remains.
// Within each segment, aliased non-atomic writes or partial atomic aliases and
// repeated descriptor state are refused. Exact atomic-sharing is permitted.
+ (instancetype)prepareScope:(KPCPUICBScope *)scope
                      buffer:(id<MTLIndirectCommandBuffer>)buffer
                     indices:(NSArray<NSNumber *> *)indices
               barrierBefore:(NSIndexSet *)barriers
                       error:(NSError **)error;
@property(nonatomic,readonly) NSArray<KPRecordedNativeCompute *> *records;
@property(nonatomic,readonly) NSDictionary *planEvidence;
// Owns creation/endEncoding of its carrier encoder. The caller still commits
// and observes completion. All data must remain valid until completion.
// On any error, discard this uncommitted command buffer; never commit/retry it.
- (BOOL)encodeToCommandBuffer:(id<MTLCommandBuffer>)commandBuffer
                    evidence:(NSDictionary **)evidence
                       error:(NSError **)error;
- (instancetype)init NS_UNAVAILABLE;
+ (instancetype)new NS_UNAVAILABLE;
@end
