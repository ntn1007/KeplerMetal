#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct Arguments { command_buffer commands [[id(0)]]; render_pipeline_state pipeline [[id(1)]]; };
kernel void probe_boundary(device Arguments &args [[buffer(0)]],device uint *out [[buffer(1)]],uint gid [[thread_position_in_grid]]) {
 if(gid>=1)return;
 render_command command(args.commands,gid);
 command.set_render_pipeline_state(args.pipeline);
 command.draw_primitives(primitive_type::triangle,0,3,1,0);
 out[gid]=0x4b505350u^gid;
}
