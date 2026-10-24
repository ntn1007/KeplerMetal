// SPDX-License-Identifier: MIT
// Each certified candidate has its own native indirect draw. GPU predicates
// activate one candidate per logical slot; pipeline/resource setters stay CPU-encoded.
#include <metal_stdlib>
#include "KeplerRenderStateRecords.h"
using namespace metal;
struct RenderStateConfig {uint logical_slots,state_count,flat_count,reserved;};
kernel void materialize_render_state_catalogue(
    device const uint *range [[buffer(0)]],
    device const KPRenderStateCommandRecord *records [[buffer(1)]],
    device const KPRenderStateTemplate *templates [[buffer(2)]],
    device uint *arguments [[buffer(3)]],
    device uint4 *witness [[buffer(4)]],
    constant RenderStateConfig &config [[buffer(5)]],
    uint entry [[thread_position_in_grid]]) {
    if(entry>=config.flat_count)return;
    uint logical=entry/config.state_count,state=entry%config.state_count;
    KPRenderStateTemplate limit=templates[entry];
    KPRenderStateCommandRecord record=records[logical];
    uint first=range[0],count=range[1];
    bool validRange=first<=config.logical_slots&&count<=config.logical_slots-min(first,config.logical_slots);
    bool known=false,reserved=record.reserved0!=0u;
    for(uint i=0u;i<6u;i++)reserved=reserved||record.reserved[i]!=0u;
    for(uint i=0u;i<config.state_count;i++)known=known||
        record.state_identity==templates[logical*config.state_count+i].state_identity;
    uint reason=0u;
    if(!limit.occupied)reason=4u;
    else if(record.magic!=KP_RENDER_STATE_COMMAND_MAGIC||reserved)reason=1u;
    else if(!known)reason=5u;
    else if(record.state_identity!=limit.state_identity)reason=6u;
    else if(record.kind!=limit.kind||record.kind>2u)reason=2u;
    else {
        uint n=record.arguments[0],instances=record.arguments[1],start=record.arguments[2];
        bool bounds=n<=limit.arguments[0]&&instances<=limit.arguments[1]&&
            record.arguments[3]==limit.arguments[3]&&record.arguments[4]==limit.arguments[4];
        if(record.kind==0u)bounds=bounds&&start>=limit.arguments[2]&&
            start-limit.arguments[2]<=limit.arguments[0]&&
            n<=limit.arguments[0]-min(start-limit.arguments[2],limit.arguments[0]);
        else bounds=bounds&&start<=limit.arguments[0]&&n<=limit.arguments[0]-min(start,limit.arguments[0]);
        if(!bounds)reason=3u;
    }
    bool selected=validRange&&logical>=first&&logical-first<count&&reason==0u;
    for(uint i=0u;i<5u;i++)arguments[entry*8u+i]=selected?record.arguments[i]:0u;
    witness[entry]=uint4(uint(validRange),uint(selected),(logical<<16u)|state,0x4b530000u|reason);
}
