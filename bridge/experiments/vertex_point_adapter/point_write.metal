// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
vertex void vs_point_write(uint id [[vertex_id]], device atomic_uint *seen [[buffer(0)]]) {
    if (id < 5) atomic_fetch_or_explicit(seen, 1u << id, memory_order_relaxed);
}
