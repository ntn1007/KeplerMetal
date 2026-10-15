#include <metal_stdlib>
using namespace metal;
struct P {uint count,seed,salt,stage;};
kernel void dependency_seed(device uint4 *dst [[buffer(0)]],device const uint4 *src [[buffer(1)]],constant P&p [[buffer(2)]],device atomic_uint *counter [[buffer(3)]],uint i [[thread_position_in_grid]]) {
 if(i>=p.count)return;
 dst[i]=uint4(i+p.seed,(i*1664525u+1013904223u)^p.seed,(i^p.seed)+p.salt,(i*17u)^p.salt);
 atomic_fetch_add_explicit(&counter[p.stage],1u,memory_order_relaxed);
}
kernel void dependency_gather(device uint4 *dst [[buffer(0)]],device const uint4 *src [[buffer(1)]],constant P&p [[buffer(2)]],device atomic_uint *counter [[buffer(3)]],uint i [[thread_position_in_grid]]) {
 if(i>=p.count)return;
 uint j=(i*5u+p.seed)&(p.count-1u);uint4 v=src[j];
 dst[i]=uint4(v.z+p.salt,v.x^p.seed,v.w+i,v.y*3u);
 atomic_fetch_add_explicit(&counter[p.stage],1u,memory_order_relaxed);
}
kernel void dependency_finish(device uint4 *dst [[buffer(0)]],device const uint4 *src [[buffer(1)]],constant P&p [[buffer(2)]],device atomic_uint *counter [[buffer(3)]],uint i [[thread_position_in_grid]]) {
 if(i>=p.count)return;
 uint4 v=src[p.count-1u-i];
 dst[i]=uint4(v.y+v.w,v.z^p.salt,v.x+i,v.w+p.seed);
 atomic_fetch_add_explicit(&counter[p.stage],1u,memory_order_relaxed);
}
