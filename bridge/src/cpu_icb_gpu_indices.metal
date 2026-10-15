#include <metal_stdlib>
using namespace metal;
struct Parameters {uint mode,seed,pad0,pad1;};
kernel void gpu_indices(device uint4 *indices [[buffer(0)]],
                        device atomic_uint *counter [[buffer(1)]],
                        constant Parameters &p [[buffer(2)]],
                        uint id [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(counter,1u,memory_order_relaxed);
    if(id==0)indices[0]=p.mode?uint4(1,1,1,p.seed):uint4(0,1,2,p.seed);
}
