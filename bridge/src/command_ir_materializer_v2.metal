#include <metal_stdlib>
using namespace metal;
struct IRConfig {uint4 selection;uint4 memory;};
struct PipelineLimitV2 {uint4 groups;uint4 local;uint4 parameters;};
// v2: reflected contiguous slots0..N-1, constants index is sealed per profile.
// All executable fields still come from owned native templates.
kernel void materialize_compute_command_ir_v2(
 device const uint *templates [[buffer(0)]],device const uint *records [[buffer(1)]],
 device atomic_uint *counts [[buffer(2)]],constant IRConfig &config [[buffer(3)]],
 device uint *destination [[buffer(4)]],device const PipelineLimitV2 *limits [[buffer(5)]],
 device uint4 *witness [[buffer(6)]],device const uint4 *resources [[buffer(7)]],
 device const uint *constantTemplates [[buffer(8)]],device uint *destinationConstants [[buffer(9)]],
 device const uint *nativeBindings [[buffer(10)]],
 uint lane [[thread_index_in_threadgroup]]) {
 uint row=config.selection.z,bank=0,resource=0,status=2;uint3 groups=uint3(0,1,1);
 device const uint *r=records+row*32u;uint requested=r[2],flags=r[1];
 if(r[0]==0x4b504952u&&flags==0u){bool empty=true;for(uint i=2;i<32u;i++)empty=empty&&(r[i]==0u);status=empty?0u:2u;}
 else if(r[0]==0x4b504952u&&r[3]==0x4b504950u&&requested<config.selection.y&&r[19]==0u){
  PipelineLimitV2 limit=limits[requested];uint n=limit.parameters.w,constantIndex=limit.parameters.z;
  uint required=n==4u?371u:115u;uint allowed=n==4u?383u:127u;
  bool valid=(n==3u||n==4u)&&constantIndex<n&&(flags&required)==required&&(flags&~allowed)==0u&&r[11]==0u;
  uint3 local=uint3(r[8],r[9],r[10]),g=uint3(r[4],r[5],r[6]);
  valid=valid&&all(local==limit.local.xyz)&&all(local>0u);
  if(r[7]==1u){valid=valid&&all((g%max(local,uint3(1u)))==0u);g/=max(local,uint3(1u));}
  else valid=valid&&r[7]==0u;
  valid=valid&&all(g>=1u)&&all(g<=limit.groups.xyz)&&g.y<=65535u&&g.z<=65535u;
  valid=valid&&(limit.local.w==0u?r[18]==0u:((flags&4u)!=0u&&r[18]==limit.local.w));
  for(uint i=20u;i<26u;i++)valid=valid&&(r[i]==0u);
  for(uint i=28u;i<32u;i++)valid=valid&&(r[i]==0u);
  uint pi=constantIndex==3u?26u:12u+constantIndex*2u;valid=valid&&r[pi]==limit.parameters.x&&r[pi+1u]==limit.parameters.y;
  if(n==3u)valid=valid&&r[26]==0u&&r[27]==0u;
  bool found=false;
  for(uint k=0u;k<min(config.memory.x,4u);k++){
   device const uint*a=(device const uint*)(resources+k*2u);bool same=true;uint mutableIndex=0u;
   for(uint slot=0u;slot<n;slot++)if(slot!=constantIndex){uint ri=slot==3u?26u:12u+slot*2u;same=same&&r[ri]==a[mutableIndex*2u]&&r[ri+1u]==a[mutableIndex*2u+1u];mutableIndex++;}
   if(same){found=true;resource=k;}
  }
  if(valid&&found){bank=requested;groups=g;status=1u;}
 }
 for(uint i=lane;i<16384u;i+=64u)destinationConstants[i]=constantTemplates[bank*16384u+i];
 threadgroup_barrier(mem_flags::mem_device);
 if(lane==0u){
  uint3 local=limits[bank].local.xyz,threads=groups*local;
  for(uint a=0u;a<3u;a++){destinationConstants[0x700u/4u+a]=groups[a];destinationConstants[0x720u/4u+a]=threads[a];destinationConstants[0x740u/4u+a]=groups[a];}
  if(status==1u){device const uint*a=nativeBindings+(bank*config.memory.x+resource)*32u;for(uint slot=0u;slot<limits[bank].parameters.w;slot++)if(slot!=limits[bank].parameters.z)for(uint word=0u;word<8u;word++)destinationConstants[slot*8u+word]=a[slot*8u+word];}
 }
 uint word=templates[bank*64u+lane];if(lane==12u)word=groups.x;if(lane==13u)word=groups.y|(groups.z<<16u);if(lane==31u)word=config.memory.y;if(lane==32u)word=(word&0xffffff00u)|(config.memory.z&255u);destination[lane]=word;
 if(lane==0u){witness[row*4u]=uint4(groups,bank);witness[row*4u+1u]=uint4(limits[bank].local.xyz,resource);witness[row*4u+2u]=uint4(status,0x4b504952u,config.memory.x,2u);witness[row*4u+3u]=uint4(0u,0u,0u,0x4b50524du);}
 atomic_fetch_add_explicit(counts+row,1u,memory_order_relaxed);
}
