// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;

struct Config { uint limit; uint nonce; uint rounds; uint reserved; };

// All communication between dispatches is atomic. Waiting is always bounded.
// Sequence tags witness interleaved lifetimes, not simultaneous SM execution.
inline void observe(uint role, device atomic_uint *sync, device uint *out,
                    constant Config &cfg) {
    uint begin = atomic_fetch_add_explicit(sync, 1u, memory_order_relaxed) + 1u;
    atomic_store_explicit(sync + 1 + role, 1u, memory_order_relaxed);
    uint seen = 0u, iterations = 0u;
    for (uint i = 0u; i < cfg.limit; ++i) {
        ++iterations;
        seen = atomic_load_explicit(sync + 2 - role, memory_order_relaxed);
        if (seen != 0u) break;
    }
    uint x = cfg.nonce ^ (role == 0u ? 0x9e3779b9u : 0x85ebca6bu);
    for (uint i = 0u; i < cfg.rounds; ++i)
        x = ((x << 7u) | (x >> 25u)) * 1664525u + 1013904223u + i;
    uint end = atomic_fetch_add_explicit(sync, 1u, memory_order_relaxed) + 1u;
    out[0] = begin; out[1] = end; out[2] = seen; out[3] = iterations;
    out[4] = x; out[5] = cfg.nonce; out[6] = role; out[7] = cfg.rounds;
}

kernel void observe_a(device atomic_uint *sync [[buffer(0)]],
                      device uint *out [[buffer(1)]],
                      constant Config &cfg [[buffer(2)]],
                      uint tid [[thread_position_in_grid]]) {
    if (tid == 0u) observe(0u, sync, out, cfg);
}

kernel void observe_b(device atomic_uint *sync [[buffer(0)]],
                      device uint *out [[buffer(1)]],
                      constant Config &cfg [[buffer(2)]],
                      uint tid [[thread_position_in_grid]]) {
    if (tid == 0u) observe(1u, sync, out, cfg);
}
