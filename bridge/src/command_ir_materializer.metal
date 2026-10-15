#include <metal_stdlib>
using namespace metal;
struct IRConfig { uint4 selection; uint4 memory; };
struct PipelineLimit {uint4 dispatch;uint4 parameters;};
// Input records carry abstract state. Every executable field comes from an
// owned native template; uninitialized/reset/unsupported records use zero CTAs.
// No resource address supplied by the producer is accepted outside the sealed
// catalogue. This first consumer supports uniform 1D shapes and shared index0.
kernel void materialize_compute_command_ir(
 device const uint *templates [[buffer(0)]],
 device const uint *records [[buffer(1)]],
 device atomic_uint *counts [[buffer(2)]],
 constant IRConfig &config [[buffer(3)]],
 device uint *destination [[buffer(4)]],
 device const PipelineLimit *limits [[buffer(5)]],
 device uint4 *witness [[buffer(6)]],
 device const uint4 *resources [[buffer(7)]],
 device const uint *constantTemplates [[buffer(8)]],
 device uint *destinationConstants [[buffer(9)]],
 uint lane [[thread_index_in_threadgroup]]) {
 uint row=config.selection.z,bank=0,groups=0,resource=0,status=2;
 device const uint *r=records+row*32u;
 uint requested=r[2],flags=r[1];
 if(r[0]==0x4b504952u&&flags==0u){
  bool empty=true;for(uint i=2;i<32u;i++)empty=empty&&(r[i]==0u);
  status=empty?0u:2u;
 }else if(r[0]==0x4b504952u&&r[3]==0x4b504950u&&requested<config.selection.y&&
          (flags&115u)==115u&&(flags&~127u)==0u&&r[19]==0u){
  PipelineLimit limit=limits[requested];
  bool sharedValid=limit.dispatch.z==0u?(r[18]==0u):((flags&4u)!=0u&&r[18]==limit.dispatch.z);
  bool valid=r[8]==limit.dispatch.y&&r[9]==1u&&r[10]==1u&&r[11]==0u&&
             r[5]==1u&&r[6]==1u&&sharedValid&&
             r[16]==limit.parameters.x&&r[17]==limit.parameters.y;
  for(uint i=20;i<32u;i++)valid=valid&&(r[i]==0u);
  uint x=r[4];
  if(r[7]==1u){valid=valid&&limit.dispatch.y!=0u&&(x%max(1u,limit.dispatch.y))==0u;x/=max(1u,limit.dispatch.y);}
  else valid=valid&&r[7]==0u;
  valid=valid&&x>=1u&&x<=limit.dispatch.x;
  bool found=false;
  for(uint k=0;k<min(config.memory.x,4u);k++){
   uint4 a=resources[k];if(r[12]==a.x&&r[13]==a.y&&r[14]==a.z&&r[15]==a.w){found=true;resource=k;}
  }
  if(valid&&found){bank=requested;groups=x;status=1u;}
 }
 for(uint i=lane;i<16384u;i+=64u)destinationConstants[i]=constantTemplates[bank*16384u+i];
 threadgroup_barrier(mem_flags::mem_device);
 // Native manifest kernels read threadgroups_per_grid from CB1[0x740].
 // Keep that shader-visible state consistent with the QMD raster dimensions.
 if(lane==0u){
  destinationConstants[0x720u/4u]=groups*limits[bank].dispatch.y;
  destinationConstants[0x724u/4u]=1u;destinationConstants[0x728u/4u]=1u;
  destinationConstants[0x740u/4u]=groups;destinationConstants[0x744u/4u]=1u;destinationConstants[0x748u/4u]=1u;
 }
 if(lane==0u&&status==1u){
  uint4 a=resources[resource];destinationConstants[2]=a.x;destinationConstants[3]=a.y;
  destinationConstants[10]=a.z;destinationConstants[11]=a.w;
 }
 uint word=templates[bank*64u+lane];
 if(lane==12u)word=groups;
 if(lane==31u)word=config.memory.y;
 if(lane==32u)word=(word&0xffffff00u)|(config.memory.z&255u);
 destination[lane]=word;
 if(lane==0u){witness[row*2u]=uint4(groups,limits[bank].dispatch.y,bank,0x4b504952u);witness[row*2u+1u]=uint4(resource,config.memory.x,status,0x4b50524du);}
 atomic_fetch_add_explicit(counts+row,1u,memory_order_relaxed);
}
