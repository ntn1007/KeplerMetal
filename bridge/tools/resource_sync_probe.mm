#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <vector>

struct Params { uint32_t seed, n; };
static void emit(NSDictionary *d) {
    NSData *b = [NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];
    fwrite(b.bytes, 1, b.length, stdout); puts(""); fflush(stdout);
}
static NSDictionary *finish(id<MTLCommandBuffer> c, bool commit = true) {
    if (commit) [c commit];
    auto until = std::chrono::steady_clock::now() + std::chrono::seconds(6);
    while (c.status != MTLCommandBufferStatusCompleted && c.status != MTLCommandBufferStatusError
           && std::chrono::steady_clock::now() < until) [NSThread sleepForTimeInterval:0.002];
    return @{ @"status":@(c.status), @"error":c.error.description ?: @"",
              @"timed_out":@(c.status != MTLCommandBufferStatusCompleted && c.status != MTLCommandBufferStatusError) };
}
static bool completed(NSDictionary *s) { return [s[@"status"] integerValue] == MTLCommandBufferStatusCompleted; }
static id<MTLComputePipelineState> pipeline(id<MTLDevice> d, id<MTLLibrary> lib, NSString *name, bool icb, NSError **error) {
    id<MTLFunction> f = [lib newFunctionWithName:name];
    if (!f) return nil;
    MTLComputePipelineDescriptor *pd = [MTLComputePipelineDescriptor new];
    pd.computeFunction = f;
    if (icb) pd.supportIndirectCommandBuffers = YES;
    return [d newComputePipelineStateWithDescriptor:pd options:MTLPipelineOptionNone reflection:nil error:error];
}
int main(int argc, char **argv) { @autoreleasepool {
    if (argc != 3) return 1;
    NSDictionary *plan = [NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[1])] options:0 error:nil];
    NSString *outDir = @(argv[2]), *kind = plan[@"kind"];
    id<MTLDevice> d = nil;
    for (id<MTLDevice> candidate in MTLCopyAllDevices()) if ([candidate.name containsString:@"880M"]) { d = candidate; break; }
    if (!d) return 2;
    NSMutableDictionary *r = [@{@"device":d.name, @"registry_id":@(d.registryID), @"kind":kind,
                               @"GPU_dispatch":@NO, @"native_only":@YES, @"uses_NAK_or_import":@NO,
                               @"own_resource_cap_bytes":@(20 * 1024 * 1024)} mutableCopy];
    __block NSString *stage = @"factory";
    @try {
        bool aliasCase = [kind isEqual:@"heap_alias"], heapCase = [kind isEqual:@"heap"] || [kind isEqual:@"heap_alias"], fenceCase = [kind isEqual:@"fence"],
             eventCase = [kind isEqual:@"event"] || [kind isEqual:@"shared_event"],
             sharedEventCase = [kind isEqual:@"shared_event"], icbCompute = [kind isEqual:@"icb_compute"],
             icbRender = [kind isEqual:@"icb_render"], negative = [kind isEqual:@"control_missing_producer"];
        id<MTLHeap> heap = nil; id<MTLFence> fence = nil; id<MTLEvent> event = nil;
        id<MTLIndirectCommandBuffer> icb = nil;
        if (heapCase) {
            MTLHeapDescriptor *hd = [MTLHeapDescriptor new]; hd.storageMode = MTLStorageModePrivate; hd.size = 16 * 1024 * 1024;
            hd.hazardTrackingMode = MTLHazardTrackingModeTracked;
            if (aliasCase) {
                MTLSizeAndAlign sa = [d heapBufferSizeAndAlignWithLength:32771u * 4u + 128u options:MTLResourceStorageModePrivate | MTLResourceHazardTrackingModeTracked];
                if (!sa.align || !sa.size) { r[@"failure_stage"] = @"heap_size_contract"; emit(r); return 8; }
                hd.size = 2u * ((sa.size + sa.align - 1u) / sa.align * sa.align);
                r[@"buffer_size_align"] = @{@"size":@(sa.size),@"align":@(sa.align)};
            }
            heap = [d newHeapWithDescriptor:hd];
            r[@"factory_selector_present"] = @([d respondsToSelector:@selector(newHeapWithDescriptor:)]);
            r[@"factory_created"] = @(heap != nil);
        } else if (fenceCase) {
            fence = [d newFence]; r[@"factory_selector_present"] = @([d respondsToSelector:@selector(newFence)]);
            r[@"factory_created"] = @(fence != nil);
        } else if (eventCase) {
            event = sharedEventCase ? [d newSharedEvent] : [d newEvent];
            r[@"factory_selector_present"] = @([d respondsToSelector:sharedEventCase ? @selector(newSharedEvent) : @selector(newEvent)]);
            r[@"factory_created"] = @(event != nil);
        } else if (icbCompute || icbRender) {
            MTLIndirectCommandBufferDescriptor *desc = [MTLIndirectCommandBufferDescriptor new];
            desc.commandTypes = icbCompute ? MTLIndirectCommandTypeConcurrentDispatch : MTLIndirectCommandTypeDraw;
            desc.inheritBuffers = NO; desc.inheritPipelineState = NO;
            if (icbCompute) desc.maxKernelBufferBindCount = 3;
            else { desc.maxVertexBufferBindCount = 0; desc.maxFragmentBufferBindCount = 1; }
            icb = [d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared];
            r[@"factory_selector_present"] = @([d respondsToSelector:@selector(newIndirectCommandBufferWithDescriptor:maxCommandCount:options:)]);
            r[@"factory_created"] = @(icb != nil);
            r[@"command_types_raw"] = @(desc.commandTypes);
        } else r[@"factory_created"] = @YES;
        if (![r[@"factory_created"] boolValue]) {
            r[@"failure_stage"] = stage; r[@"classification"] = @"factory_returned_nil"; emit(r); return 6;
        }
        if (heap) { r[@"heap_size"] = @(heap.size); r[@"heap_class"] = NSStringFromClass([heap class]); }
        if (fence) r[@"fence_class"] = NSStringFromClass([fence class]);
        if (event) r[@"event_class"] = NSStringFromClass([event class]);
        if (icb) r[@"ICB_class"] = NSStringFromClass([icb class]);
        stage = @"library"; NSError *error = nil;
        id<MTLLibrary> lib = [d newLibraryWithURL:[NSURL fileURLWithPath:plan[@"library"]] error:&error];
        if (!lib) { r[@"failure_stage"] = stage; r[@"error"] = error.description ?: @"nil"; emit(r); return 3; }
        stage = @"pipeline";
        id<MTLComputePipelineState> prod = nil, cons = nil; id<MTLRenderPipelineState> render = nil;
        if (!icbRender) {
            prod = pipeline(d, lib, @"produce", false, &error); cons = pipeline(d, lib, @"consume", icbCompute, &error);
            if (!prod || !cons) { r[@"failure_stage"] = stage; r[@"error"] = error.description ?: @"nil"; emit(r); return 4; }
            r[@"pipeline_max_threads"] = @(cons.maxTotalThreadsPerThreadgroup);
        } else {
            MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
            pd.vertexFunction = [lib newFunctionWithName:@"triangle"]; pd.fragmentFunction = [lib newFunctionWithName:@"color"];
            pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm; pd.supportIndirectCommandBuffers = YES;
            render = [d newRenderPipelineStateWithDescriptor:pd error:&error];
            if (!render) { r[@"failure_stage"] = stage; r[@"error"] = error.description ?: @"nil"; emit(r); return 4; }
        }
        id<MTLCommandQueue> q = [d newCommandQueue], q2 = eventCase ? [d newCommandQueue] : q;
        NSMutableArray *runs = [NSMutableArray new]; r[@"runs"] = runs;
        const unsigned sizes[3] = {1, 1025, 32771}, locals[3] = {64, 128, 256};
        for (unsigned iteration = 0; iteration < 3; ++iteration) { @autoreleasepool {
            Params p = {0x1234u + iteration * 37u, icbRender ? 256u : sizes[iteration]};
            unsigned local = locals[iteration]; size_t bytes = (icbRender ? 16u * 256u : size_t(p.n) * 4) + 128;
            if (!icbRender && (local > cons.maxTotalThreadsPerThreadgroup || local > prod.maxTotalThreadsPerThreadgroup)) return 5;
            std::vector<uint8_t> initial(bytes, 0xa5);
            id<MTLBuffer> params = [d newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared];
            id<MTLBuffer> host = [d newBufferWithBytes:initial.data() length:bytes options:MTLResourceStorageModeManaged];
            id<MTLBuffer> a = nil, b = nil, retainedAlias = nil; id<MTLTexture> target = nil;
            stage = @"allocation";
            MTLResourceOptions options = MTLResourceStorageModePrivate | (fenceCase ? MTLResourceHazardTrackingModeUntracked : heapCase ? MTLResourceHazardTrackingModeTracked : MTLResourceHazardTrackingModeDefault);
            if (!icbRender) {
                NSUInteger inputLength = aliasCase ? 32771u * 4u + 128u : p.n * 4u;
                NSUInteger outputLength = aliasCase ? inputLength : bytes;
                a = heap ? [heap newBufferWithLength:inputLength options:options] : [d newBufferWithLength:inputLength options:options];
                b = heap ? [heap newBufferWithLength:outputLength options:options] : [d newBufferWithLength:outputLength options:options];
                if (!a || !b || !host || !params) { r[@"failure_stage"] = stage; emit(r); return 8; }
                if (heap && (a.heap != heap || b.heap != heap)) { r[@"failure_stage"] = @"heap_ownership"; emit(r); return 8; }
                if (heap) { r[@"resources_owned_by_heap"] = @YES; r[@"heap_used_bytes"] = @(heap.usedSize); }
                r[@"input_hazard_mode"] = @(a.hazardTrackingMode); r[@"output_hazard_mode"] = @(b.hazardTrackingMode);
                if ((fence && (a.hazardTrackingMode != MTLHazardTrackingModeUntracked || b.hazardTrackingMode != MTLHazardTrackingModeUntracked)) ||
                    (heap && (a.hazardTrackingMode != MTLHazardTrackingModeTracked || b.hazardTrackingMode != MTLHazardTrackingModeTracked))) {
                    r[@"failure_stage"] = @"hazard_mode_not_honored"; emit(r); return 8;
                }
            } else {
                MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];
                td.storageMode = MTLStorageModePrivate; td.usage = MTLTextureUsageRenderTarget;
                target = [d newTextureWithDescriptor:td]; if (!target || !host || !params) { r[@"failure_stage"] = stage; emit(r); return 8; }
            }
            stage = @"upload";
            if (!icbRender) {
                id<MTLCommandBuffer> upload = [q commandBuffer]; id<MTLBlitCommandEncoder> be = [upload blitCommandEncoder];
                [be fillBuffer:a range:NSMakeRange(0, a.length) value:0];
                id<MTLBuffer> staging = [d newBufferWithBytes:initial.data() length:bytes options:MTLResourceStorageModeShared];
                [be copyFromBuffer:staging sourceOffset:0 toBuffer:b destinationOffset:0 size:bytes]; [be endEncoding];
                NSDictionary *s = finish(upload); if (!completed(s)) { r[@"failure_stage"] = stage; r[@"command"] = s; emit(r); return 9; }
                if (aliasCase) {
                    stage = @"alias_reuse";
                    id<MTLBuffer> unavailable = [heap newBufferWithLength:a.length options:options];
                    if (unavailable) { r[@"failure_stage"] = @"capacity_not_isolated"; emit(r); return 8; }
                    retainedAlias = a; [retainedAlias makeAliasable];
                    id<MTLBuffer> replacement = [heap newBufferWithLength:retainedAlias.length options:options];
                    if (!retainedAlias.isAliasable || !replacement || replacement.heap != heap) { r[@"failure_stage"] = stage; emit(r); return 8; }
                    a = replacement;
                    r[@"alias_capacity_control_nil"] = @YES; r[@"alias_old_object_retained"] = @YES; r[@"alias_reallocation_created"] = @YES;
                    r[@"alias_shared_offset_observed"] = @(retainedAlias.heapOffset == replacement.heapOffset);
                    r[@"alias_offsets"] = @[@(retainedAlias.heapOffset), @(replacement.heapOffset)];
                }
            }
            id<MTLCommandBuffer> command = [q commandBuffer], consumer = eventCase ? [q2 commandBuffer] : command;
            stage = @"encoding";
            if (!icbRender) {
                if (!negative) {
                    id<MTLComputeCommandEncoder> e = [command computeCommandEncoder]; [e setComputePipelineState:prod];
                    [e setBuffer:a offset:0 atIndex:0]; [e setBuffer:params offset:0 atIndex:2];
                    [e dispatchThreadgroups:MTLSizeMake((p.n + local - 1) / local, 1, 1) threadsPerThreadgroup:MTLSizeMake(local, 1, 1)];
                    if (fence) [e updateFence:fence]; [e endEncoding];
                }
                if (event) { [command encodeSignalEvent:event value:iteration + 1]; [consumer encodeWaitForEvent:event value:iteration + 1]; }
                id<MTLComputeCommandEncoder> e = [consumer computeCommandEncoder]; if (fence) [e waitForFence:fence];
                if (icbCompute) {
                    [icb resetWithRange:NSMakeRange(0, 1)]; id<MTLIndirectComputeCommand> indirect = [icb indirectComputeCommandAtIndex:0];
                    [indirect setComputePipelineState:cons]; [indirect setKernelBuffer:a offset:0 atIndex:0];
                    [indirect setKernelBuffer:b offset:64 atIndex:1]; [indirect setKernelBuffer:params offset:0 atIndex:2];
                    [indirect concurrentDispatchThreadgroups:MTLSizeMake((p.n + local - 1) / local, 1, 1) threadsPerThreadgroup:MTLSizeMake(local, 1, 1)];
                    [e useResource:a usage:MTLResourceUsageRead]; [e useResource:b usage:MTLResourceUsageWrite]; [e useResource:params usage:MTLResourceUsageRead];
                    [e executeCommandsInBuffer:icb withRange:NSMakeRange(0, 1)];
                } else {
                    [e setComputePipelineState:cons]; [e setBuffer:a offset:0 atIndex:0]; [e setBuffer:b offset:64 atIndex:1];
                    [e setBuffer:params offset:0 atIndex:2];
                    [e dispatchThreadgroups:MTLSizeMake((p.n + local - 1) / local, 1, 1) threadsPerThreadgroup:MTLSizeMake(local, 1, 1)];
                }
                [e endEncoding];
            } else {
                [icb resetWithRange:NSMakeRange(0, 1)]; id<MTLIndirectRenderCommand> indirect = [icb indirectRenderCommandAtIndex:0];
                [indirect setRenderPipelineState:render]; [indirect setFragmentBuffer:params offset:0 atIndex:0];
                [indirect drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1 baseInstance:0];
                MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
                pass.colorAttachments[0].texture = target; pass.colorAttachments[0].loadAction = MTLLoadActionClear;
                pass.colorAttachments[0].storeAction = MTLStoreActionStore; pass.colorAttachments[0].clearColor = MTLClearColorMake(0.25, 0.25, 0.25, 0);
                id<MTLRenderCommandEncoder> e = [command renderCommandEncoderWithDescriptor:pass];
                [e useResource:params usage:MTLResourceUsageRead stages:MTLRenderStageFragment]; [e executeCommandsInBuffer:icb withRange:NSMakeRange(0, 1)]; [e endEncoding];
            }
            stage = @"GPU_execution"; r[@"GPU_dispatch"] = @YES;
            if (eventCase) { [consumer commit]; [command commit]; } // Genuine cross-queue wait; consumer submitted first.
            NSDictionary *cs = finish(command, !eventCase), *ss = eventCase ? finish(consumer, false) : cs;
            if (!completed(cs) || !completed(ss)) { r[@"failure_stage"] = stage; r[@"producer"] = cs; r[@"consumer"] = ss; emit(r); return 9; }
            stage = @"readback"; id<MTLCommandBuffer> read = [q commandBuffer]; id<MTLBlitCommandEncoder> be = [read blitCommandEncoder];
            if (icbRender) [be copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(16,16,1)
                                   toBuffer:host destinationOffset:64 destinationBytesPerRow:256 destinationBytesPerImage:4096];
            else [be copyFromBuffer:b sourceOffset:0 toBuffer:host destinationOffset:0 size:bytes];
            [be synchronizeResource:host]; [be endEncoding]; NSDictionary *rs = finish(read);
            if (!completed(rs)) { r[@"failure_stage"] = stage; r[@"readback"] = rs; emit(r); return 9; }
            unsigned bad = 0, guards = 0; const uint8_t *data = (const uint8_t *)host.contents;
            for (unsigned i=0; i<64; ++i) guards += (data[i] != 0xa5) + (data[bytes-64+i] != 0xa5);
            for (unsigned i=0; i<p.n; ++i) {
                uint32_t expected = ((i * 1664525u) ^ p.seed) + i * 1013904223u; expected ^= p.seed * 747796405u;
                if (icbRender) expected = ((p.seed & 1u) ? 255u : 0u) | (((p.seed >> 1u) & 1u) ? 0xff00u : 0u) | (((p.seed >> 2u) & 1u) ? 0xff0000u : 0u) | 0xff000000u;
                uint32_t observed; size_t offset = icbRender ? (i / 16u) * 256u + (i % 16u) * 4u : i * 4u;
                memcpy(&observed, data+64+offset,4); bad += observed != expected;
            }
            if (icbRender) for (unsigned row=0; row<16; ++row) for (unsigned pad=64; pad<256; ++pad) guards += data[64+row*256+pad] != 0xa5;
            NSString *path = [outDir stringByAppendingPathComponent:[NSString stringWithFormat:@"output-%u.bin",iteration]];
            [[NSData dataWithBytes:data length:bytes] writeToFile:path atomically:YES];
            NSMutableDictionary *run = [@{@"iteration":@(iteration),@"seed":@(p.seed),@"elements":@(p.n),@"local":@(local),@"output_file":path,
                                           @"mismatches":@(bad),@"guard_mismatches":@(guards),@"producer":cs,@"consumer":ss,@"readback":rs} mutableCopy];
            if (sharedEventCase) run[@"GPU_signaled_value"] = @(((id<MTLSharedEvent>)event).signaledValue);
            [runs addObject:run];
            if (guards || (!negative && bad) || (negative && !bad)) { r[@"failure_stage"] = @"numeric_validation"; emit(r); return 10; }
        }}
        r[@"passed"] = @(!negative); r[@"negative_control_detected"] = @(negative); emit(r); return negative ? 10 : 0;
    } @catch (NSException *exception) {
        r[@"failure_stage"] = stage; r[@"exception"] = exception.name; r[@"reason"] = exception.reason ?: @""; emit(r); return 11;
    }
}}
