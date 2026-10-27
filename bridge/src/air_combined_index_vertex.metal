// SPDX-License-Identifier: MIT
#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct Arguments { command_buffer commands [[id(0)]]; };
kernel void probe_boundary(device Arguments &args [[buffer(0)]], device uint *out [[buffer(1)]],
 device float4 *vertices [[buffer(2)]], constant uint4 &config [[buffer(3)]],
 device ushort *index16 [[buffer(4)]], device uint *index32 [[buffer(5)]],
 uint gid [[thread_position_in_grid]]) {
 if(gid>=config.x)return;
 render_command command(args.commands,gid);
 if(config.w==1u){
  if(gid==0u)command.draw_indexed_primitives(primitive_type::triangle,6u,index16,1u,0u,gid);
  else command.draw_indexed_primitives(primitive_type::triangle,6u,index32,1u,0u,gid);
 }
 if(config.y!=0u)command.set_vertex_buffer(vertices+config.z,0u);
 if(config.w!=1u){
  if(gid==0u)command.draw_indexed_primitives(primitive_type::triangle,6u,index16,1u,0u,gid);
  else command.draw_indexed_primitives(primitive_type::triangle,6u,index32,1u,0u,gid);
 }
 if(config.w==2u)command.reset();
 out[gid]=0x4b504d00u^gid^config.w;
}
