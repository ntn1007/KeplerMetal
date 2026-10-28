// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
struct P { uint seed, n, local, groups, variant; };
kernel void test(constant P& p [[buffer(0)]], device uint4* out [[buffer(1)]],
                 device atomic_uint* global [[buffer(3)]],
                 uint i [[thread_position_in_grid]],
                 uint tid [[thread_index_in_threadgroup]],
                 uint group [[threadgroup_position_in_grid]]) {
    uint initial = p.seed + group * 0x10001u;
    uint replacement = p.seed ^ 0x55667788u;
    threadgroup atomic_uint shared[4];
    threadgroup atomic_uint* a = &shared[3];
    if (tid == 0) atomic_store_explicit(a, initial, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint compare = initial ^ (p.variant ? 1u : 0u);
    bool success = atomic_compare_exchange_weak_explicit(a, &compare, replacement,
                                                          memory_order_relaxed, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint final = atomic_load_explicit(a, memory_order_relaxed);
    out[i] = uint4(compare, uint(success), final, i);
}
