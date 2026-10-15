#include <metal_stdlib>
using namespace metal;
struct KeplerParameters {
    ulong addresses[4];
    uint grid[3];
    uint block[3];
};
// Establish a normal Metal constant-buffer binding and output residency.
// This reference body is deliberately different from add_buffers.
kernel void add_buffers(constant KeplerParameters &p [[buffer(0)]],
                        device float *output [[buffer(1)]],
                        uint index [[thread_position_in_grid]]) {
    if (index < p.grid[0]) {
        ulong bits = p.addresses[0] + p.addresses[1] + p.addresses[2] + p.addresses[3];
        uint dimensions = p.grid[1] + p.grid[2] + p.block[0] + p.block[1] + p.block[2];
        output[index] = float(bits & 65535ul) + float(dimensions);
    }
}
