// SPDX-License-Identifier: MIT
// Explicit KeplerMetal source ABI; not Apple's native command-buffer ABI.
#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;

struct ImageCommandArguments {
    command_buffer commands [[id(0)]];
    compute_pipeline_state pipeline [[id(1)]];
    device uint *arguments [[id(2)]];
    device uint4 *output [[id(3)]];
    device const uint *parameters [[id(4)]];
};

kernel void encode_image_command(device ImageCommandArguments &a [[buffer(0)]],
                                uint gid [[thread_position_in_grid]]) {
    if (gid) return;
    compute_command c(a.commands, 0u);
    c.reset();
    c.set_compute_pipeline_state(a.pipeline);
    // Both addresses belong to the sealed host catalogue. The producer only
    // records the selected address; the materializer validates it before use.
    uint bank=(a.parameters[0]^a.parameters[1]^a.parameters[2])&1u;
    ulong alternate=ulong(a.parameters[4])|(ulong(a.parameters[5])<<32u);
    device uint *imageArguments=bank?reinterpret_cast<device uint*>(alternate):a.arguments;
    c.set_kernel_buffer(imageArguments, 0u);
    c.set_kernel_buffer(a.output, 1u);
    c.set_kernel_buffer(a.parameters, 2u);
    c.concurrent_dispatch_threadgroups(uint3((a.parameters[0]+31u)/32u,1u,1u),
                                      uint3(32u,1u,1u));
}
