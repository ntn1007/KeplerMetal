// SPDX-License-Identifier: MIT
// Public call sites, compiled with the opt-in native CommandIR header.
// Writes inert record DATA only; this probe never submits these records.
#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct NativeRecordArguments {
    command_buffer commands [[id(0)]];
    compute_pipeline_state pipeline [[id(1)]];
    device uint *storage [[id(2)]];
    constant uint *constants [[id(3)]];
    command_buffer other [[id(4)]];
};
kernel void native_command_record_case(device NativeRecordArguments &args [[buffer(0)]],
    constant uint &operation [[buffer(1)]],uint gid [[thread_position_in_grid]]) {
    if(gid)return;
    compute_command a(args.commands,0),b(args.commands,1),foreign(args.other,0);
    if(operation==0 || (operation>=13 && operation<=16) || operation==20){a.reset();return;}
    if(operation==1 || operation==4 || operation==22){
        a.reset();a.set_compute_pipeline_state(args.pipeline);
        a.set_kernel_buffer(args.storage,0u);a.set_kernel_buffer(args.constants,1u);
        a.set_kernel_buffer(args.storage+7,2u);a.set_kernel_buffer(args.constants+3,3u);
        a.concurrent_dispatch_threadgroups(uint3(2,3,4),uint3(32,1,1));
        a.set_threadgroup_memory_length(128u,0u);a.set_barrier();
        if(operation==4)a.clear_barrier();if(operation==22)a.copy_command(a);return;
    }
    if(operation==2){a.reset();a.concurrent_dispatch_threads(uint3(64,4,2),uint3(32,2,1));return;}
    if(operation==3){a.reset();a.set_compute_pipeline_state(args.pipeline);a.set_barrier();b.copy_command(a);a.reset();return;}
    if(operation==5){a.set_compute_pipeline_state(args.pipeline);return;}
    if(operation==6){a.reset();a.set_compute_pipeline_state(compute_pipeline_state(0));return;}
    if(operation==7){a.reset();a.set_compute_pipeline_state((args.pipeline&0xffffffff00000000ul)|3ul);return;}
    if(operation==8){a.reset();a.set_kernel_buffer(args.storage,4u);return;}
    if(operation==9){a.reset();a.set_threadgroup_memory_length(128u,1u);return;}
    if(operation==10){b.reset();b.copy_command(a);return;}
    if(operation==11){foreign.reset();b.reset();b.copy_command(foreign);return;}
    if(operation==12){compute_command invalid(args.commands,8);invalid.reset();return;}
    if(operation==17){a.reset();a.set_stage_in_region(uint3(1,2,3),uint3(4,5,6));return;}
    if(operation==18){a.reset();a.set_compute_pipeline_state(args.pipeline);return;}
    if(operation==19){a.reset();a.set_kernel_buffer(args.storage,3u);return;}
    if(operation==21){a.reset();a.set_compute_pipeline_state(compute_pipeline_state(0));a.clear_barrier();return;}
}
