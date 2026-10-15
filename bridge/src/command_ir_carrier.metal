#include <metal_stdlib>
using namespace metal;
struct ImportABI { uint root[2]; uint grid[3]; uint block[3]; };
// Native negative control uses the existing qualified 128-byte shared-memory
// carrier pattern. Imported code uses no shared bytes; the allocation remains.
kernel void command_ir_carrier(constant ImportABI &p [[buffer(0)]],
                               device uint4 *out [[buffer(1)]],
                               uint i [[thread_position_in_grid]],
                               uint tid [[thread_index_in_threadgroup]]) {
    threadgroup uint memory[32];
    memory[tid]=p.grid[0]^0x7a11beefu;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if(i<p.grid[0])out[i]=uint4(memory[tid],0u,0xdeadbeefu,i);
}
