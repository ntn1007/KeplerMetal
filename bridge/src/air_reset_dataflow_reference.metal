// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
struct Context { uint magic,version,capacity,recordBytes;ulong records,reserved; };
inline void reset_project(ulong address,uint index){
    if(!address)return;
    device Context *c=reinterpret_cast<device Context*>(address);
    if(c->magic!=0x4b505243u||c->version!=1||!c->capacity||c->capacity>16||c->recordBytes!=64||
       c->reserved||index>=c->capacity||!c->records||c->records>1099511626752ul||(c->records&15ul))return;
    device uint4 *record=reinterpret_cast<device uint4*>(c->records+ulong(index)*64ul);
    for(uint i=0;i<4;i++)record[i]=uint4(0);
}
kernel void probe_boundary(device ulong *root [[buffer(0)]],device uint *out [[buffer(1)]],
                          device const uint *indices [[buffer(2)]],constant uint4 &config [[buffer(3)]],
                          uint gid [[thread_position_in_grid]]){
    if(gid>=config.x)return;
    uint index=indices[gid];uint x=(gid*1664525u+config.y)^index;
    if((x&config.z)==0u){reset_project(root[0],index);x^=0xa511e9b3u;}
    else{x+=0x7f4a7c15u;}
    uint shift=(gid&15u)+1u;
    out[gid]=((x<<shift)|(x>>(32u-shift)))^(index*0x9e3779b9u);
}
