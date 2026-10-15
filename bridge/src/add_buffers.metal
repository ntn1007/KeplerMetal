#include <metal_stdlib>
using namespace metal;

kernel void add_buffers(device const float *a [[buffer(0)]],
                        device const float *b [[buffer(1)]],
                        device float *output [[buffer(2)]],
                        constant uint &count [[buffer(3)]],
                        uint index [[thread_position_in_grid]]) {
    if (index < count)
        output[index] = a[index] + b[index];
}
