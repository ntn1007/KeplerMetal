// SPDX-License-Identifier: MIT
#include <metal_stdlib>
#include "KeplerRenderStateRecords.h"
using namespace metal;
kernel void generate_render_state_records(device const uint *input [[buffer(0)]],
    device uint *range [[buffer(1)]],device uint *counter [[buffer(2)]],
    constant uint4 &config [[buffer(3)]],
    device const KPRenderStateIdentity *identities [[buffer(4)]],
    device KPRenderStateCommandRecord *records [[buffer(5)]],
    device const KPRenderStateIdentity *foreignIdentities [[buffer(6)]],
    uint slot [[thread_position_in_grid]]) {
    if(slot>=4u)return;
    uint value=input[(config.x*5u+3u)%16u];
    KPRenderStateCommandRecord record={};
    if(slot!=2u){
        uint kind=slot==0u?0u:slot==1u?1u:2u;
        uint choice=config.w?config.w-1u:(value>>(kind+3u))&1u;
        record.magic=KP_RENDER_STATE_COMMAND_MAGIC;record.kind=kind;
        record.state_identity=identities[choice];
        record.arguments[0]=3u;record.arguments[1]=1u;
        record.arguments[2]=(slot==0u?5u:0u)+3u*((value>>kind)&1u);
        record.arguments[3]=slot==0u?0u:slot==1u?2u:0xfffffffeu;
        record.arguments[4]=slot==0u?0u:slot==1u?1u:2u;
        if(config.y==1u&&slot==1u)record.state_identity=0ul;
        if(config.y==2u&&slot==3u)record.state_identity=foreignIdentities[choice];
        if(config.y==3u&&slot==0u)record.kind=1u;
        if(config.y==4u&&slot==1u)record.arguments[2]=0xfffffffeu;
        if(config.y==5u&&slot==3u)record.reserved[0]=1u;
        if(config.y==6u&&slot==0u)record.state_identity^=0x100000000ul;
    }
    records[slot]=record;
    if(slot==0u){range[0]=0u;range[1]=4u;counter[0]=value^0x4b505357u;}
}
