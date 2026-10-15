#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct GridArguments {
 command_buffer commands [[id(0)]];
 compute_pipeline_state pipeline [[id(1)]];
 device uint *coordinates [[id(2)]];
 device uint *geometry [[id(3)]];
 device atomic_uint *counter [[id(4)]];
 constant uint *parameters [[id(5)]];
};
#define CONFIGURE(C) \
 C.reset();C.set_compute_pipeline_state(args.pipeline); \
 C.set_kernel_buffer(args.coordinates,0u);C.set_kernel_buffer(args.geometry,1u); \
 C.set_kernel_buffer(args.counter,2u);C.set_kernel_buffer(args.parameters,3u); \
 uint3 groups=uint3(1u+args.coordinates[0]%args.parameters[4],1u+args.geometry[0]%args.parameters[5],1u+args.coordinates[1]%args.parameters[6]); \
 uint3 local=uint3(args.parameters[7],args.parameters[8],args.parameters[9]); \
 C.concurrent_dispatch_threadgroups(groups,local);
kernel void encode_grid_basic(device GridArguments&args [[buffer(0)]],uint i [[thread_position_in_grid]]){compute_command c(args.commands,i);CONFIGURE(c)}
kernel void encode_grid_threads(device GridArguments&args [[buffer(0)]],uint i [[thread_position_in_grid]]){
 compute_command c(args.commands,i);c.reset();c.set_compute_pipeline_state(args.pipeline);c.set_kernel_buffer(args.coordinates,0u);c.set_kernel_buffer(args.geometry,1u);c.set_kernel_buffer(args.counter,2u);c.set_kernel_buffer(args.parameters,3u);
 uint3 groups=uint3(1u+args.coordinates[0]%args.parameters[4],1u+args.geometry[0]%args.parameters[5],1u+args.coordinates[1]%args.parameters[6]);uint3 local=uint3(args.parameters[7],args.parameters[8],args.parameters[9]);c.concurrent_dispatch_threads(groups*local,local);
}
kernel void encode_grid_barrier(device GridArguments&args [[buffer(0)]],uint i [[thread_position_in_grid]]){compute_command c(args.commands,i);CONFIGURE(c)c.set_barrier();}
kernel void encode_grid_copy(device GridArguments&args [[buffer(0)]],uint i [[thread_position_in_grid]]){if(i)return;compute_command a(args.commands,0u),b(args.commands,1u);CONFIGURE(a)b.copy_command(a);a.reset();}
kernel void encode_grid_reset(device GridArguments&args [[buffer(0)]],uint i [[thread_position_in_grid]]){compute_command c(args.commands,i);c.reset();}
