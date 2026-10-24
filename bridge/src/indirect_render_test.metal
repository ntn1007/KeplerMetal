// SPDX-License-Identifier: MIT
#include <metal_stdlib>
#include "KeplerRenderCommandRecords.h"
using namespace metal;
kernel void generate_render_range(device const uint *input [[buffer(0)]],
    device uint *range [[buffer(1)]], device uint *counter [[buffer(2)]],
    constant uint4 &config [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
    if(gid)return;
    uint value=input[(config.x*5u+3u)%16u], first=0u, count=config.z;
    switch(config.y){
        case 1:first=value%config.z;count=1u;break;
        case 2:count=1u+value%config.z;break;
        case 3:first=value%config.z;count=config.z-first;break;
        case 4:first=value%config.z;count=0u;break;
        case 5:first=config.z+1u;count=0u;break;
        case 6:first=0xfffffffeu;count=3u;break;
    }
    range[0]=first;range[1]=count;counter[0]=value^0x4b505257u;
}
struct MarkerVertex {float4 position;float4 color;};
struct MarkerOut {float4 position [[position]];float4 color;};
vertex MarkerOut vs_range_marker(uint vid [[vertex_id]],
    device const MarkerVertex *vertices [[buffer(0)]],
    device const float4 *parameters [[buffer(1)]]) {
    MarkerOut out;out.position=vertices[vid].position;
    out.color=float4(.875f,.25f,parameters[0].z,1.f);return out;
}
fragment float4 fs_range_marker(MarkerOut in [[stage_in]], device const float4 *parameters [[buffer(0)]]){return float4(in.color.x,parameters[0].z,in.color.z,1.f);}

kernel void generate_render_records(device const uint *input [[buffer(0)]],
    device uint *range [[buffer(1)]],device uint *counter [[buffer(2)]],
    constant uint4 &config [[buffer(3)]],
    device KPRenderCommandRecord *records [[buffer(4)]],
    uint slot [[thread_position_in_grid]]) {
    if(slot>=4u)return;
    uint value=input[(config.x*5u+3u)%16u];
    KPRenderCommandRecord record={};
    if(slot!=2u){
        record.magic=KP_RENDER_COMMAND_MAGIC;
        record.kind=slot==0u?0u:slot==1u?1u:2u;
        record.arguments[0]=3u;record.arguments[1]=1u;
        record.arguments[2]=(slot==0u?5u:0u)+3u*((value>>record.kind)&1u);
        record.arguments[3]=slot==0u?0u:slot==1u?2u:0xfffffffeu;
        record.arguments[4]=slot==0u?0u:slot==1u?1u:2u;
        // Valid shader inputs intentionally exercise the validator. These
        // rejected scalar records never become unchecked native draw arguments.
        if(config.y==1u&&slot==1u)record.magic=0u;
        if(config.y==2u&&slot==3u)record.kind=1u;
        if(config.y==3u&&slot==0u)record.arguments[0]=0xfffffffeu;
        if(config.y==4u&&slot==1u)record.arguments[2]=0xfffffffeu;
        if(config.y==5u&&slot==3u)record.arguments[3]=0u;
        if(config.y==6u&&slot==0u)record.arguments[1]=2u;
    }
    records[slot]=record;
    if(slot==0u){range[0]=0u;range[1]=4u;counter[0]=value^0x4b505257u;}
}
