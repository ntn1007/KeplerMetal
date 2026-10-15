#include <metal_stdlib>
using namespace metal;
kernel void consume_command(device uint4 *out [[buffer(0)]],
                            device atomic_uint *counter [[buffer(1)]],
                            constant uint *p [[buffer(2)]],
                            threadgroup uint *dynamic [[threadgroup(0)]],
                            uint3 gid [[thread_position_in_grid]],
                            uint tid [[thread_index_in_threadgroup]]) {
    threadgroup uint fixed[128]; // 512B + the producer's 48640B = 48KiB
    fixed[tid]=p[0]^tid;
    dynamic[tid]=p[0]+tid;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint i=gid.x+p[1]*gid.y;
    out[i]=uint4(i,fixed[tid],dynamic[tid],gid.y);
    atomic_fetch_add_explicit(counter,1u,memory_order_relaxed);
}
