// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
vertex void vs_point_transform(uint id [[vertex_id]], const device uint *source [[buffer(0)]], device atomic_uint *destination [[buffer(1)]]) {
    if (id < 256) atomic_store_explicit(destination + id, source[id] * 3u + 7u, memory_order_relaxed);
}
