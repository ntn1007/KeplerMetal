// SPDX-License-Identifier: MIT
#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct Arguments { command_buffer commands [[id(0)]]; };
kernel void probe_boundary(device Arguments &args [[buffer(0)]],
                          device uint *out [[buffer(1)]],
                          device const uint *indices [[buffer(2)]],
                          constant uint4 &config [[buffer(3)]],
                          uint gid [[thread_position_in_grid]]) {
    if(gid>=config.x)return;
    uint index=indices[gid];
    uint x=(gid*1664525u+config.y)^index;
    render_command command(args.commands,index);
    if(config.w==2u)command.reset();
    if((x&config.z)==0u){
        command.draw_primitives(primitive_type::triangle,
            5u+3u*((x>>3u)&1u),3u*((x>>4u)&3u),(x>>6u)&1u,(x>>8u)&3u);
        x^=0xa511e9b3u;
    }else{command.reset();x+=0x7f4a7c15u;}
    if(config.w==1u)command.reset();
    uint shift=(gid&15u)+1u;
    out[gid]=((x<<shift)|(x>>(32u-shift)))^(index*0x9e3779b9u);
}
