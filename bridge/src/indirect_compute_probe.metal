#include <metal_stdlib>
using namespace metal;
struct P { uint seed,groups,local,max_n; };
kernel void produce_grid(device uint *args [[buffer(0)]],constant P&p [[buffer(1)]],uint tid [[thread_position_in_grid]]) {
    if(tid==0){args[0]=p.groups;args[1]=1;args[2]=1;}
}
kernel void consume_grid(device uint4 *out [[buffer(0)]],device atomic_uint *count [[buffer(1)]],constant P&p [[buffer(2)]],
                        uint3 position [[thread_position_in_grid]],uint3 grid [[threadgroups_per_grid]],uint3 local [[threads_per_threadgroup]]) {
    uint i=position.x;
    atomic_fetch_add_explicit(count,1u,memory_order_relaxed);
    if(i<p.max_n)out[i]=uint4((p.seed*1664525u)^(i*1013904223u),i,grid.x|(grid.y<<16)|(grid.z<<24),local.x);
}
