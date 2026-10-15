#include <metal_stdlib>
using namespace metal;

// The host dispatches exactly the number of allocated active elements.
kernel void add_buffers(device const float *a [[buffer(0)]],
                        device const float *b [[buffer(1)]],
                        device float *output [[buffer(2)]],
                        constant uint &count [[buffer(3)]],
                        uint index [[thread_position_in_grid]]) {
    output[index] = a[index] + b[index];
}
