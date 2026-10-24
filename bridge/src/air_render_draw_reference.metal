// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
struct Context { uint magic,version,capacity,recordBytes;ulong records,reserved; };
inline device uint *record_at(ulong address,uint index){
    if(!address)return nullptr;
    device const Context *c=reinterpret_cast<device const Context*>(address);
    if(c->magic!=0x4b505243u||c->version!=1||!c->capacity||c->capacity>16||c->recordBytes!=64||
       c->reserved||index>=c->capacity||!c->records||c->records>1099511626752ul||(c->records&15ul))return nullptr;
    return reinterpret_cast<device uint*>(c->records+ulong(index)*64ul);
}
inline void reset_at(ulong address,uint index){
    device uint *record=record_at(address,index);if(!record)return;
    for(uint i=0;i<16;i++)record[i]=0;
}
inline void draw_at(ulong address,uint index,uint first,uint count,uint instances,uint base){
    device uint *record=record_at(address,index);if(!record)return;
    uint identityLow=record[8],identityHigh=record[9];
    for(uint i=0;i<16;i++)record[i]=0;
    record[0]=0x4b505353u;record[2]=count;record[3]=instances;record[4]=first;record[6]=base;
    record[8]=identityLow;record[9]=identityHigh;
}
kernel void probe_boundary(device const ulong *root [[buffer(0)]],device uint *out [[buffer(1)]],
                          device const uint *indices [[buffer(2)]],constant uint4 &config [[buffer(3)]],
                          uint gid [[thread_position_in_grid]]){
    if(gid>=config.x)return;
    uint index=indices[gid],x=(gid*1664525u+config.y)^index;
    if(config.w==2u)reset_at(root[0],index);
    if((x&config.z)==0u){
        draw_at(root[0],index,5u+3u*((x>>3u)&1u),3u*((x>>4u)&3u),(x>>6u)&1u,(x>>8u)&3u);
        x^=0xa511e9b3u;
    }else{reset_at(root[0],index);x+=0x7f4a7c15u;}
    if(config.w==1u)reset_at(root[0],index);
    uint shift=(gid&15u)+1u;
    out[gid]=((x<<shift)|(x>>(32u-shift)))^(index*0x9e3779b9u);
}
