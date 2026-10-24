// SPDX-License-Identifier: MIT
// A bounded execution-range prepass; no CPU readback of the requested range.
#include <metal_stdlib>
using namespace metal;
struct RangeConfig { uint slots, reserved0, reserved1, reserved2; };
kernel void materialize_render_icb_range(
    device const uint *range [[buffer(0)]],
    device const uint *templates [[buffer(1)]],
    device uint *arguments [[buffer(2)]],
    device uint4 *witness [[buffer(3)]],
    constant RangeConfig &config [[buffer(4)]],
    uint slot [[thread_position_in_grid]]) {
    if (slot >= config.slots) return;
    uint first=range[0], count=range[1];
    bool valid=first<=config.slots && count<=config.slots-min(first,config.slots);
    bool selected=valid && slot>=first && slot-first<count && templates[slot*8u+6u]!=0u;
    // First5 words contain either MTLDrawPrimitivesIndirectArguments or
    // MTLDrawIndexedPrimitivesIndirectArguments. The final3 are guard words.
    for(uint i=0u;i<5u;i++)arguments[slot*8u+i]=selected?templates[slot*8u+i]:0u;
    witness[slot]=uint4(uint(valid),uint(selected),templates[slot*8u+5u],0x4b505247u);
}
