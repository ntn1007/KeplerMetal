// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;

struct Params { uint seed, local, pattern, variant; };

kernel void divergence_case(constant Params& p [[buffer(0)]],
                            device uint4* out [[buffer(1)]],
                            uint i [[thread_position_in_grid]],
                            uint tid [[thread_index_in_threadgroup]],
                            uint group [[threadgroup_position_in_grid]]) {
    threadgroup atomic_uint cells[1024];
    threadgroup uint guards[4];
    uint initial=p.seed+group*0x10001u+tid*13u;
    atomic_store_explicit(&cells[tid],initial,memory_order_relaxed);
    if(tid==0) for(uint k=0;k<4;k++) guards[k]=p.seed^group^(0x13570000u+k*0x101u);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    bool active=p.pattern==1u || (p.pattern==2u && (tid&1u)==0u) ||
                (p.pattern==3u && tid<(p.local+1u)/2u);
    uint compare=initial^(p.variant?1u:0u);
    bool success=false;
    if(active) success=atomic_compare_exchange_weak_explicit(&cells[tid],&compare,
        initial^0x55667788u,memory_order_relaxed,memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint final=atomic_load_explicit(&cells[tid],memory_order_relaxed);
    uint guard=0;
    for(uint k=0;k<4;k++) guard|=guards[k]^(p.seed^group^(0x13570000u+k*0x101u));
    out[i]=uint4(compare,uint(success),final,i^0x6d2b79f5u^(active?0x80000000u:0u)^guard);
}
