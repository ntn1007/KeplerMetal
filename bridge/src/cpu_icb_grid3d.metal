#include <metal_stdlib>
using namespace metal;
struct Parameters{uint count,seed,reserved0,reserved1;};
kernel void grid_coordinates(device uint4 *coordinates [[buffer(0)]],
    device uint4 *geometry [[buffer(1)]], device atomic_uint *counter [[buffer(2)]],
    constant Parameters &p [[buffer(3)]], uint3 gid [[thread_position_in_grid]],
    uint3 lane [[thread_position_in_threadgroup]], uint3 group [[threadgroup_position_in_grid]],
    uint3 groups [[threadgroups_per_grid]], uint3 local [[threads_per_threadgroup]]) {
    uint3 full=groups*local;
    uint index=gid.x+full.x*(gid.y+full.y*gid.z);
    atomic_fetch_add_explicit(counter,1u,memory_order_relaxed);
    if(index<p.count){coordinates[index]=uint4(gid,index);geometry[index]=uint4(
        lane.x|(lane.y<<10u)|(lane.z<<20u),group.x|(group.y<<10u)|(group.z<<20u),
        groups.x|(groups.y<<10u)|(groups.z<<20u),
        (local.x|(local.y<<10u)|(local.z<<20u))^p.seed);}
}
