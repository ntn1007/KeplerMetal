#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct StageArguments {
 command_buffer commands [[id(0)]];
 compute_pipeline_state pipeline [[id(1)]];
 device uint4 *dst [[id(2)]];
 device const uint4 *src [[id(3)]];
 constant uint *parameters [[id(4)]];
 device atomic_uint *counter [[id(5)]];
};
inline void encode_stages(device StageArguments*args,uint skipped,bool barrier){
 for(uint stage=0u;stage<3u;stage++){
  compute_command c(args[stage].commands,stage);c.reset();if(stage==skipped)continue;
  c.set_compute_pipeline_state(args[stage].pipeline);
  c.set_kernel_buffer(args[stage].dst,0u);c.set_kernel_buffer(args[stage].src,1u);
  c.set_kernel_buffer(args[stage].parameters,2u);c.set_kernel_buffer(args[stage].counter,3u);
  uint count=args[stage].parameters[0],local=args[stage].parameters[4];
  c.concurrent_dispatch_threadgroups(uint3((count+local-1u)/local,1u,1u),uint3(local,1u,1u));
  if(barrier)c.set_barrier();
 }
}
kernel void encode_dataflow_basic(device StageArguments*args [[buffer(0)]],uint i [[thread_position_in_grid]]){if(i)return;encode_stages(args,~0u,false);}
kernel void encode_dataflow_barrier(device StageArguments*args [[buffer(0)]],uint i [[thread_position_in_grid]]){if(i)return;encode_stages(args,~0u,true);}
kernel void encode_dataflow_no_seed(device StageArguments*args [[buffer(0)]],uint i [[thread_position_in_grid]]){if(i)return;encode_stages(args,0u,false);}
kernel void encode_dataflow_no_gather(device StageArguments*args [[buffer(0)]],uint i [[thread_position_in_grid]]){if(i)return;encode_stages(args,1u,false);}
kernel void encode_dataflow_no_finish(device StageArguments*args [[buffer(0)]],uint i [[thread_position_in_grid]]){if(i)return;encode_stages(args,2u,false);}
kernel void encode_dataflow_copy(device StageArguments*args [[buffer(0)]],uint i [[thread_position_in_grid]]){if(i)return;encode_stages(args,~0u,false);compute_command src(args[0].commands,0u),dst(args[0].commands,3u);dst.copy_command(src);src.reset();}
