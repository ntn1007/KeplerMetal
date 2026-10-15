#include <metal_stdlib>
using namespace metal;
// One native buffer binding only. The compiled control mutates that buffer;
// imported command producers read its address from the real resource CB1.
kernel void command_ir_native_root_carrier(device uint *root [[buffer(0)]],
    uint i [[thread_position_in_grid]], uint tid [[thread_index_in_threadgroup]]) {
    threadgroup uint shared[32];
    shared[tid & 31u] = root[tid & 7u] ^ 0x7a11beefu;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (i == 0u) root[0] = shared[0] ^ 0xa511b00fu;
}
