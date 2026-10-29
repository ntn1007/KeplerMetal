// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
kernel void invert_luma(texture2d<float,access::read> source [[texture(0)]], texture2d<float,access::write> destination [[texture(1)]], uint2 p [[thread_position_in_grid]]) {
    if (p.x >= destination.get_width() || p.y >= destination.get_height()) return;
    uint v=uint(round(source.read(p).x*255.0f));
    destination.write(float4(float(255u-v)/255.0f,0.0f,0.0f,1.0f),p);
}
kernel void copy_chroma(texture2d<float,access::read> source [[texture(0)]], texture2d<float,access::write> destination [[texture(1)]], uint2 p [[thread_position_in_grid]]) {
    if (p.x >= destination.get_width() || p.y >= destination.get_height()) return;
    float2 uv=source.read(p).xy;
    destination.write(float4(uv,0.0f,1.0f),p);
}
