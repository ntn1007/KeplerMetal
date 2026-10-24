// SPDX-License-Identifier: MIT
// GPU records contain scalars only. Host-owned templates seal resource state
// and the maximum geometry/instance footprint; no GPU record selects addresses.
#include <metal_stdlib>
#include "KeplerRenderCommandRecords.h"
using namespace metal;
struct RenderRecordConfig { uint slots, reserved0, reserved1, reserved2; };
kernel void materialize_render_command_records(
    device const uint *range [[buffer(0)]],
    device const KPRenderCommandRecord *records [[buffer(1)]],
    device const uint *templates [[buffer(2)]],
    device uint *arguments [[buffer(3)]],
    device uint4 *witness [[buffer(4)]],
    constant RenderRecordConfig &config [[buffer(5)]],
    uint slot [[thread_position_in_grid]]) {
    if(slot>=config.slots)return;
    uint first=range[0],count=range[1];
    bool validRange=first<=config.slots&&count<=config.slots-min(first,config.slots);
    device const uint *limit=templates+slot*8u;
    KPRenderCommandRecord record=records[slot];
    uint reason=0u;
    if(!limit[6])reason=4u;
    else if(record.magic!=KP_RENDER_COMMAND_MAGIC||record.reserved)reason=1u;
    else if(record.kind!=limit[5]||record.kind>2u)reason=2u;
    else {
        uint n=record.arguments[0],instances=record.arguments[1],start=record.arguments[2];
        bool bounds=n<=limit[0]&&instances<=limit[1]&&
            record.arguments[3]==limit[3]&&record.arguments[4]==limit[4];
        if(record.kind==0u){
            // Subtract only after the lower-bound check: no wrapping add.
            bounds=bounds&&start>=limit[2]&&start-limit[2]<=limit[0]&&
                n<=limit[0]-min(start-limit[2],limit[0]);
        }else bounds=bounds&&start<=limit[0]&&n<=limit[0]-min(start,limit[0]);
        if(!bounds)reason=3u;
    }
    bool selected=validRange&&slot>=first&&slot-first<count&&reason==0u;
    for(uint i=0u;i<5u;i++)arguments[slot*8u+i]=selected?record.arguments[i]:0u;
    witness[slot]=uint4(uint(validRange),uint(selected),limit[5],0x4b520000u|reason);
}
