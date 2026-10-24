// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
kernel void generate_render_range(device const uint *input [[buffer(0)]],
    device uint *range [[buffer(1)]], device uint *counter [[buffer(2)]],
    constant uint4 &config [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
    if(gid)return;
    uint value=input[(config.x*5u+3u)%16u], first=0u, count=config.z;
    switch(config.y){
        case 1:first=value%config.z;count=1u;break;
        case 2:count=1u+value%config.z;break;
        case 3:first=value%config.z;count=config.z-first;break;
        case 4:first=value%config.z;count=0u;break;
        case 5:first=config.z+1u;count=0u;break;
        case 6:first=0xfffffffeu;count=3u;break;
    }
    range[0]=first;range[1]=count;counter[0]=value^0x4b505257u;
}
struct MarkerVertex {float4 position;float4 color;};
struct MarkerOut {float4 position [[position]];float4 color;};
vertex MarkerOut vs_range_marker(uint vid [[vertex_id]],
    device const MarkerVertex *vertices [[buffer(0)]],
    device const float4 *parameters [[buffer(1)]]) {
    MarkerOut out;out.position=vertices[vid].position;
    out.color=float4(.875f,.25f,parameters[0].z,1.f);return out;
}
fragment float4 fs_range_marker(MarkerOut in [[stage_in]], device const float4 *parameters [[buffer(0)]]){return float4(in.color.x,parameters[0].z,in.color.z,1.f);}
