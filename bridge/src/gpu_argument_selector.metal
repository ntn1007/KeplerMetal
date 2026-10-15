#include <metal_stdlib>
using namespace metal;
// The choice comes from a GPU reduction of a Private input dataset. No CPU
// choice or resource handle is supplied. Both candidate tables are preencoded
// with MTLArgumentEncoder; the selector only copies their opaque words.
kernel void produce_argument_bank(device const uint *values [[buffer(0)]],
                                  device uint4 *choice [[buffer(1)]],
                                  device atomic_uint *counter [[buffer(2)]],
                                  constant uint4 &configuration [[buffer(3)]],
                                  device uint *indices [[buffer(4)]],
                                  uint lane [[thread_index_in_threadgroup]]) {
    threadgroup uint partial[32];
    partial[lane] = ((values[lane] * 1664525u + 1013904223u) ^ configuration.x) & 255u;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    if (lane == 0) {
        uint sum = 0;
        for (uint i = 0; i < 32; ++i) sum += partial[i];
        *choice = uint4(sum & 1u, sum, 0x4b504742u, configuration.x);
        for (uint i = 0; i < 6; ++i) indices[i] = i + configuration.y;
    }
}
kernel void select_argument_words_from_gpu(device const uint *banks [[buffer(0)]],
                                           device uint *destination [[buffer(1)]],
                                           device atomic_uint *counter [[buffer(2)]],
                                           device const uint4 *choice [[buffer(3)]],
                                           constant uint4 &configuration [[buffer(4)]],
                                           uint i [[thread_position_in_grid]]) {
    // Clamp the bank in GPU code: every value selects one of the two valid
    // tables, and no CPU readback of the choice is needed before rendering.
    uint bank = choice->x & 1u;
    if (i < configuration.y) {
        destination[i] = banks[bank * 64 + i];
        atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    }
}
