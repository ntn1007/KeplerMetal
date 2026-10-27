// SPDX-License-Identifier: MIT
#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct Arguments { command_buffer commands [[id(0)]]; };
kernel void probe_boundary(device Arguments &args [[buffer(0)]], device uint *out [[buffer(1)]],
                           device float4 *fragmentData [[buffer(2)]], constant uint4 &config [[buffer(3)]],
                           uint gid [[thread_position_in_grid]]) {
 if(gid>=config.x)return;
 render_command command(args.commands,gid);
 if(config.y)command.set_fragment_buffer(fragmentData+config.z,config.w);
 command.draw_primitives(primitive_type::triangle,0,3,1,0);
 out[gid]=0x4b504600u^gid;
}
