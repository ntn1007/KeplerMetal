#include <metal_stdlib>
using namespace metal;
struct Parameters { uint seed, groups, local, max_n, scratch_words; };

kernel void manifest_mix(device uint4 *out [[buffer(0)]],
    device atomic_uint *count [[buffer(1)]], constant Parameters &p [[buffer(2)]],
    uint3 position [[thread_position_in_grid]], uint3 grid [[threadgroups_per_grid]],
    uint3 local [[threads_per_threadgroup]]) {
    uint i=position.x,x=(p.seed*1664525u)^(i*1013904223u);
    atomic_fetch_add_explicit(count,1u,memory_order_relaxed);
    if(i<p.max_n)out[i]=uint4((x<<13u)|(x>>19u),i,
        grid.x|(grid.y<<16u)|(grid.z<<24u),local.x);
}

kernel void manifest_dynamic(device uint4 *out [[buffer(0)]],
    device atomic_uint *count [[buffer(1)]], constant Parameters &p [[buffer(2)]],
    threadgroup uint *scratch [[threadgroup(0)]],
    uint3 position [[thread_position_in_grid]], uint3 grid [[threadgroups_per_grid]],
    uint3 local [[threads_per_threadgroup]], uint3 lane3 [[thread_position_in_threadgroup]],
    uint3 group3 [[threadgroup_position_in_grid]]) {
    uint lane=lane3.x;
    for(uint j=lane;j<p.scratch_words;j+=local.x)
        scratch[j]=(p.seed*1664525u)^(group3.x*1013904223u)^(j*2246822519u);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint sum=0;
    for(uint j=lane;j<p.scratch_words;j+=local.x)sum+=scratch[j];
    atomic_fetch_add_explicit(count,1u,memory_order_relaxed);
    uint i=position.x;
    if(i<p.max_n)out[i]=uint4(sum,i,grid.x|(grid.y<<16u)|(grid.z<<24u),local.x);
}
