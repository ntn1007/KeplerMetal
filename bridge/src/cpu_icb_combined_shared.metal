#include <metal_stdlib>
using namespace metal;
struct P { uint seed, groups, local, max_n, scratch_words; };

// Both arrays are fully initialized cooperatively. Different value families
// and cross-array reads make an overlapping dynamic base observable.
#define SHARED_KERNEL(NAME, WORDS) \
kernel void NAME(device uint4 *out [[buffer(0)]], \
    device atomic_uint *count [[buffer(1)]], constant P &p [[buffer(2)]], \
    threadgroup uint *dynamic [[threadgroup(0)]], \
    uint3 position [[thread_position_in_grid]], uint3 lane3 [[thread_position_in_threadgroup]], \
    uint3 group3 [[threadgroup_position_in_grid]], uint3 local [[threads_per_threadgroup]]) { \
    threadgroup uint fixed[WORDS]; \
    uint lane=lane3.x; \
    for(uint j=lane;j<WORDS;j+=local.x) \
        fixed[j]=(p.seed*1664525u)^(group3.x*1013904223u)^(j*2246822519u)^0x73193211u; \
    for(uint j=lane;j<p.scratch_words;j+=local.x) \
        dynamic[j]=(p.seed*22695477u)^(group3.x*747796405u)^(j*2891336453u)^0x11998877u; \
    threadgroup_barrier(mem_flags::mem_threadgroup); \
    uint a=0,b=0; \
    for(uint j=lane;j<p.scratch_words;j+=local.x)a+=dynamic[j]; \
    for(uint j=lane;j<WORDS;j+=local.x)b+=fixed[j]; \
    uint witness=fixed[(lane+1u)%WORDS]^dynamic[(lane*3u+7u)%p.scratch_words]; \
    atomic_fetch_add_explicit(count,1u,memory_order_relaxed); \
    if(position.x<p.max_n)out[position.x]=uint4(a,b,position.x,witness); \
}

SHARED_KERNEL(shared_mix_s128,128u)
SHARED_KERNEL(shared_mix_s1024,1024u)
SHARED_KERNEL(shared_mix_s4096,4096u)
