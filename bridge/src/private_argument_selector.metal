#include <metal_stdlib>
using namespace metal;
// Opaque words are produced by MTLArgumentEncoder. This kernel selects one
// of two complete, certified tables; it does not invent resource handles.
kernel void select_argument_words(device const uint *banks [[buffer(0)]],
                                  device uint *destination [[buffer(1)]],
                                  device atomic_uint *counter [[buffer(2)]],
                                  constant uint4 &configuration [[buffer(3)]],
                                  uint i [[thread_position_in_grid]]) {
    if (i < configuration.y) {
        destination[i] = banks[configuration.x * 64 + i];
        atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    }
}
