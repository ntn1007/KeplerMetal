#include "gpu_command_geometry.metal"
struct BindingConfig { uint4 selection; uint4 memory; };
#if KP_NATIVE_ICB
struct BindingBank {
    array<device uint4*,4> outputs [[id(0)]];
    array<device atomic_uint*,4> counters [[id(4)]];
};
#endif

// Resource addresses are sealed by the host, not supplied by arbitrary shader
// data. Choice, prefix grid and resource-bank selection are computed on GPU.
kernel void generate_bound_command_from_gpu(
#if KP_NATIVE_ICB
    device NativeCommands &args [[buffer(0)]], device BindingBank &resources [[buffer(7)]],
#else
    device const uint *templates [[buffer(0)]], device uint *destination [[buffer(4)]],
    device const uint4 *resources [[buffer(7)]],
    device const uint *constantTemplates [[buffer(8)]], device uint *destinationConstants [[buffer(9)]],
#endif
    device const uint4 *choices [[buffer(1)]], device atomic_uint *counts [[buffer(2)]],
    constant BindingConfig &config [[buffer(3)]], device const uint4 *limits [[buffer(5)]],
    device uint4 *generated [[buffer(6)]], uint lane [[thread_index_in_threadgroup]]) {
    uint4 p=config.selection;
    uint bank=choices[p.z].x%p.y;
    uint groups=1u+(choices[p.z].y/3u)%clamp(limits[bank].x,1u,7u);
    uint resource=(choices[p.z].y/34u)%clamp(config.memory.x,1u,4u);
#if KP_NATIVE_ICB
    if(lane==0){
        compute_command src(args.commands,bank),dst(args.commands,p.w);
        dst.copy_command(src);
        dst.set_kernel_buffer(resources.outputs[resource],0u);
        dst.set_kernel_buffer(resources.counters[resource],1u);
        dst.concurrent_dispatch_threadgroups(uint3(groups,1u,1u),uint3(limits[bank].y,1u,1u));
    }
#else
    for(uint i=lane;i<16384u;i+=64u)destinationConstants[i]=constantTemplates[bank*16384u+i];
    threadgroup_barrier(mem_flags::mem_device);
    if(lane==0){
        uint4 addresses=resources[resource];
        destinationConstants[2]=addresses.x;destinationConstants[3]=addresses.y;
        destinationConstants[10]=addresses.z;destinationConstants[11]=addresses.w;
    }
    uint word=templates[bank*64u+lane];
    if(lane==12u)word=groups;
    if(lane==31u)word=config.memory.y;
    if(lane==32u)word=(word&0xffffff00u)|(config.memory.z&255u);
    destination[lane]=word;
#endif
    if(lane==0){
        generated[p.z*2u]=uint4(groups,limits[bank].y,bank,0x4b504742u);
        generated[p.z*2u+1u]=uint4(resource,config.memory.x,0u,0x4b50524bu);
    }
    atomic_fetch_add_explicit(counts+p.z,1u,memory_order_relaxed);
}
