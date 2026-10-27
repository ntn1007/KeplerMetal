// SPDX-License-Identifier: MIT
#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct Arguments {command_buffer commands [[id(0)]];};
kernel void probe_boundary(device Arguments &args [[buffer(0)]],device uint *out [[buffer(1)]],
 device const uint *indices [[buffer(2)]],constant uint4 &config [[buffer(3)]],
 device ushort *index16 [[buffer(4)]],device uint *index32 [[buffer(5)]],uint gid [[thread_position_in_grid]]) {
 if(gid>=config.x)return;
 uint slot=indices[gid],x=(gid*1664525u+config.y)^slot;
 render_command command(args.commands,slot);
 if(config.w==2u)command.reset();
 if((x&config.z)==0u){
  uint first=3u*((x>>3u)&1u),count=3u*((x>>4u)&3u),instances=(x>>6u)&1u;
  if((gid&1u)==0u)command.draw_indexed_primitives(primitive_type::triangle,count,index16+first,instances,2u,1u);
  else command.draw_indexed_primitives(primitive_type::triangle,count,index32+first,instances,uint(-2),2u);
  x^=0xa511e9b3u;
 }else{command.reset();x+=0x7f4a7c15u;}
 if(config.w==3u){
  uint lastFirst=3u-3u*((((gid*1664525u+config.y)^slot)>>3u)&1u);
  if((gid&1u)==0u)command.draw_indexed_primitives(primitive_type::triangle,3u,index16+lastFirst,1u,2u,1u);
  else command.draw_indexed_primitives(primitive_type::triangle,3u,index32+lastFirst,1u,uint(-2),2u);
 }
 if(config.w==1u)command.reset();
 uint shift=(gid&15u)+1u;
 out[gid]=((x<<shift)|(x>>(32u-shift)))^(slot*0x9e3779b9u);
}
