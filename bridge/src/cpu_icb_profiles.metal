#include <metal_stdlib>
using namespace metal;
struct P { uint seed, groups, local, max_n; };

kernel void profile_integer(device uint4 *out [[buffer(0)]],
    device atomic_uint *count [[buffer(1)]], constant P &p [[buffer(2)]],
    uint3 position [[thread_position_in_grid]], uint3 grid [[threadgroups_per_grid]],
    uint3 local [[threads_per_threadgroup]]) {
    uint i=position.x;
    atomic_fetch_add_explicit(count,1u,memory_order_relaxed);
    if(i<p.max_n) out[i]=uint4((p.seed*1664525u)^(i*1013904223u),i,
        grid.x|(grid.y<<16)|(grid.z<<24),local.x);
}

kernel void profile_fma(device uint4 *out [[buffer(0)]],
    device atomic_uint *count [[buffer(1)]], constant P &p [[buffer(2)]],
    uint3 position [[thread_position_in_grid]], uint3 grid [[threadgroups_per_grid]],
    uint3 local [[threads_per_threadgroup]]) {
    uint i=position.x;
    atomic_fetch_add_explicit(count,1u,memory_order_relaxed);
    if(i<p.max_n) {
        // All values are exactly representable, so the oracle need not assume
        // an unqualified rounding, NaN, subnormal or transcendental behavior.
        float f=fma(float(i&31u),0.5f,float(p.seed&255u));
        out[i]=uint4(as_type<uint>(f),i,grid.x|(grid.y<<16)|(grid.z<<24),local.x);
    }
}

kernel void profile_shared(device uint4 *out [[buffer(0)]],
    device atomic_uint *count [[buffer(1)]], constant P &p [[buffer(2)]],
    uint3 position [[thread_position_in_grid]], uint3 grid [[threadgroups_per_grid]],
    uint3 local [[threads_per_threadgroup]], uint3 lane3 [[thread_position_in_threadgroup]]) {
    threadgroup uint scratch[128];
    uint lane=lane3.x;
    uint i=position.x;
    scratch[lane]=(p.seed*1664525u)^(i*1013904223u);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint neighbor=scratch[(lane+1u)%local.x];
    atomic_fetch_add_explicit(count,1u,memory_order_relaxed);
    if(i<p.max_n) out[i]=uint4(neighbor,i,grid.x|(grid.y<<16)|(grid.z<<24),local.x);
}
