// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
kernel void write_luma(texture2d<float,access::write> plane [[texture(0)]], uint2 p [[thread_position_in_grid]]) {
    if (p.x >= plane.get_width() || p.y >= plane.get_height()) return;
    uint v=16u+(p.x*3u+p.y*5u+7u)%220u;
    plane.write(float4(float(v)/255.0f,0.0f,0.0f,1.0f),p);
}
kernel void write_chroma(texture2d<float,access::write> plane [[texture(0)]], uint2 p [[thread_position_in_grid]]) {
    if (p.x >= plane.get_width() || p.y >= plane.get_height()) return;
    uint u=16u+(p.x*7u+p.y*11u+3u)%225u;
    uint v=16u+(p.x*5u+p.y*13u+9u)%225u;
    plane.write(float4(float(u)/255.0f,float(v)/255.0f,0.0f,1.0f),p);
}
