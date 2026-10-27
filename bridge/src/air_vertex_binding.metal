#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct Arguments { command_buffer commands [[id(0)]]; };
kernel void probe_boundary(device Arguments &args [[buffer(0)]], device uint *out [[buffer(1)]], device float4 *vertices [[buffer(2)]], constant uint4 &config [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 if (gid >= config.x) return;
 render_command cmd(args.commands, gid);
 if (config.y) cmd.set_vertex_buffer(vertices + config.z, config.w);
 cmd.draw_primitives(primitive_type::triangle, 0, 3, 1, 0);
 out[gid] = gid ^ config.z;
}
