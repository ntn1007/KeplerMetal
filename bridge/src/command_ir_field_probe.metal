#include <metal_stdlib>
using namespace metal;
// Controlled mutations of inert IR DATA. Never modifies machine code or QMDs.
kernel void mutate_command_ir_data(device uint *record [[buffer(0)]],
                                   constant uint2 &mutation [[buffer(1)]]) {
    if(mutation.x<32u)record[mutation.x]=mutation.y;
}
