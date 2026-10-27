// SPDX-License-Identifier: MIT
#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct Arguments { command_buffer commands [[id(0)]]; render_pipeline_state pipeline [[id(1)]]; };
kernel void probe_boundary(device Arguments &args [[buffer(0)]], device uint *out [[buffer(1)]],
 device float4 *vertices [[buffer(2)]], constant uint4 &config [[buffer(3)]],
 device ushort *index16 [[buffer(4)]], device uint *index32 [[buffer(5)]],
 uint gid [[thread_position_in_grid]]) {
 if(gid>=config.x)return;
 render_command command(args.commands,gid);
 if(config.w==2u){
  if(gid==0u)command.draw_indexed_primitives(primitive_type::triangle,6u,index16,1u,0u,gid);
  else command.draw_indexed_primitives(primitive_type::triangle,6u,index32,1u,0u,gid);
 }
 if(config.w==1u){
  if(config.y&2u)command.set_render_pipeline_state(args.pipeline);
  if(config.y&1u)command.set_vertex_buffer(vertices+config.z,0u);
 }else{
  if(config.y&1u)command.set_vertex_buffer(vertices+config.z,0u);
  if(config.y&2u)command.set_render_pipeline_state(args.pipeline);
 }
 if(config.w!=2u){
  if(gid==0u)command.draw_indexed_primitives(primitive_type::triangle,6u,index16,1u,0u,gid);
  else command.draw_indexed_primitives(primitive_type::triangle,6u,index32,1u,0u,gid);
 }
 if(config.w==3u)command.reset();
 out[gid]=0x4b505400u^gid^config.w;
}
