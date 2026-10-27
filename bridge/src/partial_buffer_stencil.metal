// SPDX-License-Identifier: MIT
// Bounded, immutable-input uint4 neighbor transform for the experimental ICB.
#include <metal_stdlib>
using namespace metal;
struct Parameters { uint count, seed, reserved0, reserved1; };
kernel void partial_buffer_stencil(device const uint4 *source [[buffer(0)]],
    device uint4 *output [[buffer(1)]], device atomic_uint *counter [[buffer(2)]],
    constant Parameters &p [[buffer(3)]], uint3 gid [[thread_position_in_grid]],
    uint3 grid [[threads_per_grid]]) {
    uint index = gid.x + grid.x * (gid.y + grid.y * gid.z);
    uint total = grid.x * grid.y * grid.z;
    atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    if (index < p.count) {
        uint4 a = source[index], b = source[(index + 1u) % total];
        output[index] = uint4(a.x ^ b.y ^ p.seed, a.y + b.z,
                              a.z ^ b.w, a.w + b.x + p.seed);
    }
}
