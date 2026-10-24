// SPDX-License-Identifier: MIT
// Inert record data only. These records are never submitted as GPU commands.
#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
kernel void stable_pipeline_record_case(command_buffer context [[buffer(0)]],
 constant ulong *ids [[buffer(1)]],device uint *parameters [[buffer(2)]],
 constant uint &op [[buffer(3)]],uint gid [[thread_position_in_grid]]) {
 if(gid)return;
 compute_command a(context,0),b(context,1);
 if(op==10){compute_command invalid(context,2);invalid.reset();return;}
 a.reset();if(op==11)return;
 if(op==7 || op==8 || op==15 || op==16){a.set_compute_pipeline_state(op==8?0x4b50495000000000ul:op>=15?ids[0]:ids[2]);return;}
 if(op==9){a.set_compute_pipeline_state(ids[0]);a.set_compute_pipeline_state(ids[2]);return;}
 if(op==3)a.set_kernel_buffer(parameters+32,2u);
 a.set_compute_pipeline_state(op==6?ids[1]:ids[0]);
 if(op==17){a.concurrent_dispatch_threadgroups(uint3(1),uint3(16,1,1));return;}
 if(op==4){a.concurrent_dispatch_threadgroups(uint3(1),uint3(16,1,1));a.set_kernel_buffer(parameters+32,2u);return;}
 device uint*p=parameters;uint local=32,groups=op==2?4:1;
 if(op==1 || op==3 || op==12){p=parameters+32;local=16;}
 if(op==6){p=parameters+16;local=64;}
 if(op==18)p=parameters+1;
 a.set_kernel_buffer(p,2u);
 if(op==14)a.set_threadgroup_memory_length(16u,0u);
 if(op==3)a.concurrent_dispatch_threads(uint3(16,1,1),uint3(16,1,1));
 else if(op==19)a.concurrent_dispatch_threads(uint3(33,1,1),uint3(32,1,1));
 else a.concurrent_dispatch_threadgroups(uint3(groups,1,1),uint3(local,1,1));
 if(op==5){a.set_kernel_buffer(parameters+32,2u);a.concurrent_dispatch_threadgroups(uint3(1),uint3(16,1,1));}
 if(op==12){b.copy_command(a);a.reset();}
}
