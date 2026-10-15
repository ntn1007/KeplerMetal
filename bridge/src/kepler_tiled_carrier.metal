#include <metal_stdlib>
using namespace metal;
struct Parameters {ulong addresses[4];uint grid[3];uint block[3];};
kernel void add_buffers(constant Parameters &p [[buffer(0)]],
                        device float *output [[buffer(1)]],
                        uint tid [[thread_index_in_threadgroup]],
                        uint index [[thread_position_in_grid]]) {
    threadgroup float a[256], b[256];
    a[tid] = float(tid+1); b[tid] = float(tid+2);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    float value = a[(tid+16)&255] + b[(tid+32)&255];
    if(index < p.grid[0]) output[index] = value;
}
