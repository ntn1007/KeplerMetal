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
#define CONFIGURE(C) \
 C.reset(); \
 C.set_compute_pipeline_state(args.pipeline); \
 C.set_kernel_buffer(args.output,0u); \
 C.set_kernel_buffer(args.counter,1u); \
 C.set_kernel_buffer(args.parameters,2u); \
 C.set_threadgroup_memory_length(48640u,0u); \
 C.concurrent_dispatch_threadgroups(uint3(1u,1u,1u),uint3(32u,1u,1u)); \
 C.set_stage_in_region(uint3(3u,2u,1u),uint3(17u,4u,2u)); \
 C.set_barrier();
kernel void encode_public_barrier(device CommandArguments &args [[buffer(0)]],uint i [[thread_position_in_grid]]) {
 compute_command c(args.commands,i);CONFIGURE(c)
}
kernel void encode_public_clear(device CommandArguments &args [[buffer(0)]],uint i [[thread_position_in_grid]]) {
 compute_command c(args.commands,i);CONFIGURE(c)
 c.clear_barrier();
}
kernel void encode_public_threads(device CommandArguments &args [[buffer(0)]],uint i [[thread_position_in_grid]]) {
 compute_command c(args.commands,i);CONFIGURE(c)
 // The last dispatch wins and keeps the unit (grid threads versus groups).
 c.concurrent_dispatch_threads(uint3(97u,2u,1u),uint3(32u,1u,1u));
}
kernel void encode_public_copy(device CommandArguments &args [[buffer(0)]],uint i [[thread_position_in_grid]]) {
 if(i)return;
 compute_command source(args.commands,0u),destination(args.commands,1u);
 CONFIGURE(source)
 destination.copy_command(source);
 // Copy must survive later reset of its source; it is not a pointer alias.
 source.reset();
}
