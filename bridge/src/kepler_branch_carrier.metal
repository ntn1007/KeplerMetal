#include <metal_stdlib>
using namespace metal;
struct Parameters {ulong addresses[4];uint grid[3];uint block[3];};
kernel void add_buffers(constant Parameters &p [[buffer(0)]],
                        device float *output [[buffer(1)]],
                        uint index [[thread_position_in_grid]]) {
    if (index >= p.grid[0]) return;
    float value = 0;
    uint iterations = (index & 1) ? p.block[0] : 1;
    for (uint j = 0; j < iterations; j++)
        value = value * 1.0001f + 1.0f;
    output[index] = value;
}
