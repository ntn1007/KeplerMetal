#include <metal_stdlib>
using namespace metal;
#ifndef CARRIER_LOCAL_MAX
#define CARRIER_LOCAL_MAX 32
#endif
struct ImportABI {ulong addresses[4];uint grid[3];uint block[3];};
// A deliberately different native result detects accidentally executing the
// original carrier rather than the imported, translated AIR kernel.
kernel void cas_carrier(constant ImportABI &p [[buffer(0)]],
                        device uint4 *out [[buffer(1)]],
                        uint i [[thread_position_in_grid]],
                        uint tid [[thread_index_in_threadgroup]]) {
    threadgroup uint memory[CARRIER_LOCAL_MAX];
    memory[tid] = p.grid[0] ^ 0x7a11beefu;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (i < p.grid[0]) out[i] = uint4(memory[tid], 0u, 0xdeadbeefu, i);
}
