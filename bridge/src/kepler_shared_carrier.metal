#include <metal_stdlib>
using namespace metal;
struct Parameters {ulong addresses[4];uint grid[3];uint block[3];};
kernel void add_buffers(constant Parameters &p [[buffer(0)]],
                        device float *output [[buffer(1)]],
                        uint tid [[thread_index_in_threadgroup]],
                        uint group [[threadgroup_position_in_grid]]) {
    threadgroup float shared[128];
    shared[tid] = float(tid + 1);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride=64; stride; stride/=2) {
        if (tid < stride) shared[tid] += shared[tid+stride];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (tid == 0 && group < p.grid[0]) output[group] = shared[0];
}
