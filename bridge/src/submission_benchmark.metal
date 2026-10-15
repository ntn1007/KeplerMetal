#include <metal_stdlib>
using namespace metal;
struct Params { uint seed, n, step; };
kernel void benchmark_produce(device uint *a [[buffer(0)]], constant Params &p [[buffer(2)]],
                              device atomic_uint *counter [[buffer(3)]], device uint *audit [[buffer(4)]],
                              uint i [[thread_position_in_grid]]) {
    if (i < p.n) a[i] = (i * 1664525u) ^ p.seed;
    if (i == 0) { audit[p.step * 2] = p.seed; atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed); }
}
kernel void benchmark_consume(device const uint *a [[buffer(0)]], device uint *out [[buffer(1)]],
                              constant Params &p [[buffer(2)]], device atomic_uint *counter [[buffer(3)]],
                              device uint *audit [[buffer(4)]], uint i [[thread_position_in_grid]]) {
    if (i < p.n) out[i] = (a[i] + i * 1013904223u) ^ (p.seed * 747796405u);
    if (i == 0) { audit[p.step * 2 + 1] = out[0]; atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed); }
}
