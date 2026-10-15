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

// Public MSL producer: this is compiled/inspected offline before any GPU use.
kernel void encode_public_compute_command(device CommandArguments &args [[buffer(0)]],
                                         uint index [[thread_position_in_grid]]) {
    compute_command command(args.commands,index);
    command.reset();
    command.set_compute_pipeline_state(args.pipeline);
    command.set_kernel_buffer(args.output,0u);
    command.set_kernel_buffer(args.counter,1u);
    command.set_kernel_buffer(args.parameters,2u);
    command.set_threadgroup_memory_length(48640u,0u);
    command.concurrent_dispatch_threadgroups(uint3(1u,1u,1u),uint3(32u,1u,1u));
}
