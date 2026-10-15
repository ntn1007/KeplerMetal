#include <metal_stdlib>
using namespace metal;
struct Parameters { uint count; float scale; uint seed; uint reserved; };
kernel void bound_axpy(device float4 *out [[buffer(0)]],
    device const float4 *a [[buffer(1)]], device const float4 *b [[buffer(2)]],
    constant Parameters &p [[buffer(3)]], uint3 position [[thread_position_in_grid]]) {
    uint i=position.x;
    if(i<p.count)out[i]=fma(a[i],float4(p.scale),b[i]);
}
