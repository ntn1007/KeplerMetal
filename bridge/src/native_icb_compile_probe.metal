// SPDX-License-Identifier: MIT
// Construction-only probe; this program is never dispatched by its host.
#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct NativeICBArguments { command_buffer commands [[id(0)]]; };
kernel void reset_native_icb_slot(device NativeICBArguments &args [[buffer(0)]],
                                 uint gid [[thread_position_in_grid]]) {
    if(gid==0){compute_command command(args.commands,0);command.reset();}
}
