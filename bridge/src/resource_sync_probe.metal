#include <metal_stdlib>
using namespace metal;
struct Params { uint seed, n; };
kernel void produce(device uint *a [[buffer(0)]], constant Params &p [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    if (i < p.n) a[i] = (i * 1664525u) ^ p.seed;
}
kernel void consume(device const uint *a [[buffer(0)]], device uint *out [[buffer(1)]],
                    constant Params &p [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    if (i < p.n) out[i] = (a[i] + i * 1013904223u) ^ (p.seed * 747796405u);
}
vertex float4 triangle(uint i [[vertex_id]]) {
    const float2 positions[3] = {float2(-1, -1), float2(3, -1), float2(-1, 3)};
    return float4(positions[i], 0, 1);
}
fragment float4 color(constant Params &p [[buffer(0)]]) {
    return float4(float(p.seed & 1u), float((p.seed >> 1u) & 1u), float((p.seed >> 2u) & 1u), 1);
}
