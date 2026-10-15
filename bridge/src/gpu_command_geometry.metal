#include "gpu_command_selector.metal"

// Only the X group count changes. Pipeline, buffers, local size and shared
// allocation stay inside the retained, validated native template contract.
kernel void generate_grid_prefix_from_gpu(
#if KP_NATIVE_ICB
    device NativeCommands &args [[buffer(0)]],
#else
    device const uint *templates [[buffer(0)]], device uint *destination [[buffer(4)]],
#endif
    device const uint4 *choices [[buffer(1)]], device atomic_uint *counts [[buffer(2)]],
    constant uint4 &p [[buffer(3)]], device const uint4 *limits [[buffer(5)]],
    device uint4 *generated [[buffer(6)]], uint lane [[thread_index_in_threadgroup]]) {
    uint bank=choices[p.z].x%p.y;
    uint maximum=clamp(limits[bank].x,1u,7u);
    uint groups=1u+(choices[p.z].y/3u)%maximum;
#if KP_NATIVE_ICB
    if(lane==0){
        compute_command src(args.commands,bank),dst(args.commands,p.w);
        dst.copy_command(src);
        dst.concurrent_dispatch_threadgroups(uint3(groups,1u,1u),uint3(limits[bank].y,1u,1u));
    }
#else
    // The native recorder verifies this word against the original dispatch.
    destination[lane]=lane==12u?groups:templates[bank*64u+lane];
#endif
    if(lane==0)generated[p.z]=uint4(groups,limits[bank].y,bank,0x4b504747u);
    atomic_fetch_add_explicit(counts+p.z,1u,memory_order_relaxed);
}
