#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct CommandArguments {
 command_buffer commands [[id(0)]];
 compute_pipeline_state pipeline [[id(1)]];
 device uint *output [[id(2)]];
 device atomic_uint *counter [[id(3)]];
 constant uint *parameters [[id(4)]];
};
// Registration supplies local/shared bounds; the grid is computed from a live
// Private output word. CPU supplies neither a resolved grid nor command records.
#define CONFIGURE(C) \
 C.reset(); \
 C.set_compute_pipeline_state(args.pipeline); \
 C.set_kernel_buffer(args.output,0u); \
 C.set_kernel_buffer(args.counter,1u); \
 C.set_kernel_buffer(args.parameters,2u); \
 C.set_threadgroup_memory_length(args.parameters[4]*4u,0u); \
 C.concurrent_dispatch_threadgroups(uint3(1u+args.output[0]%args.parameters[1],1u,1u),uint3(args.parameters[2],1u,1u));
kernel void encode_runtime_basic(device CommandArguments &args [[buffer(0)]],uint i [[thread_position_in_grid]]) {
 compute_command c(args.commands,i);CONFIGURE(c)
}
kernel void encode_runtime_barrier(device CommandArguments &args [[buffer(0)]],uint i [[thread_position_in_grid]]) {
 compute_command c(args.commands,i);CONFIGURE(c) c.set_barrier();
}
kernel void encode_runtime_clear(device CommandArguments &args [[buffer(0)]],uint i [[thread_position_in_grid]]) {
 compute_command c(args.commands,i);CONFIGURE(c) c.set_barrier();c.clear_barrier();
}
kernel void encode_runtime_copy(device CommandArguments &args [[buffer(0)]],uint i [[thread_position_in_grid]]) {
 if(i)return;compute_command source(args.commands,0u),destination(args.commands,1u);
 CONFIGURE(source) destination.copy_command(source);source.reset();
}
kernel void encode_runtime_reset(device CommandArguments &args [[buffer(0)]],uint i [[thread_position_in_grid]]) {
 compute_command c(args.commands,i);c.reset();
}
