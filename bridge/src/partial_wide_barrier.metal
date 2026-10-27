// SPDX-License-Identifier: MIT
// Bounded diagnostic only: every physical group must have 1..128 threads.
#include <metal_stdlib>
using namespace metal;
struct Parameters { uint count, seed, reserved0, reserved1; };
static inline uint pack3(uint3 v) { return v.x | (v.y << 10) | (v.z << 20); }
kernel void partial_builtin_barrier(device uint4 *coordinates [[buffer(0)]],
    device uint4 *geometry [[buffer(1)]], device atomic_uint *counter [[buffer(2)]],
    constant Parameters &p [[buffer(3)]], uint3 gid [[thread_position_in_grid]],
    uint3 lane [[thread_position_in_threadgroup]], uint3 group [[threadgroup_position_in_grid]],
    uint3 groups [[threadgroups_per_grid]], uint3 actual [[threads_per_threadgroup]],
    uint3 nominal [[dispatch_threads_per_threadgroup]], uint3 grid [[threads_per_grid]],
    uint laneIndex [[thread_index_in_threadgroup]]) {
    threadgroup uint scratch[128];
    uint n = actual.x * actual.y * actual.z;
    scratch[laneIndex] = laneIndex ^ p.seed;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint witness = scratch[(laneIndex + 32) % n];
    uint index = gid.x + grid.x * (gid.y + grid.y * gid.z);
    atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    if (index < p.count) {
        coordinates[index] = uint4(pack3(gid), pack3(lane), pack3(group), pack3(groups));
        geometry[index] = uint4(pack3(actual), pack3(nominal), pack3(grid), witness);
    }
}
