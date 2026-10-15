#include <metal_stdlib>
using namespace metal;
#ifndef KP_NATIVE_ICB
#define KP_NATIVE_ICB 0
#endif
#if KP_NATIVE_ICB
#include <metal_command_buffer>
struct NativeCommands { command_buffer commands [[id(0)]]; };
#endif

// Input datasets and choices are Private. The CPU provides data, a nonce and
// bounds, not a resolved choice or expected result.
kernel void produce_command_choices(device const uint *values [[buffer(0)]],
    device uint4 *choices [[buffer(1)]], device atomic_uint *counts [[buffer(2)]],
    constant uint4 &p [[buffer(3)]], uint lane [[thread_index_in_threadgroup]],
    uint row [[threadgroup_position_in_grid]]) {
    threadgroup uint partial[32];
    uint x=values[row*32+lane];
    partial[lane]=((x*1664525u+1013904223u)^p.x^(row*97u))&255u;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_add_explicit(counts+row,1u,memory_order_relaxed);
    if(lane==0){uint sum=0;for(uint j=0;j<32;j++)sum+=partial[j];choices[row]=uint4(sum%p.y,sum,0x4b504743u,p.x);}
}

kernel void select_command_from_gpu(
#if KP_NATIVE_ICB
    device NativeCommands &args [[buffer(0)]],
#else
    device const uint *templates [[buffer(0)]], device uint *destination [[buffer(4)]],
#endif
    device const uint4 *choices [[buffer(1)]], device atomic_uint *counts [[buffer(2)]],
    constant uint4 &p [[buffer(3)]], uint lane [[thread_index_in_threadgroup]]) {
    uint bank=choices[p.z].x%p.y;
#if KP_NATIVE_ICB
    if(lane==0){compute_command src(args.commands,bank);compute_command dst(args.commands,p.w);dst.copy_command(src);}
#else
    destination[lane]=templates[bank*64+lane];
#endif
    atomic_fetch_add_explicit(counts+p.z,1u,memory_order_relaxed);
}
