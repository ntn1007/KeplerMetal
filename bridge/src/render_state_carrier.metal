#include <metal_stdlib>
using namespace metal;
struct StateVertex {float4 position [[position]];};
static StateVertex state_vertex(uint index) {
    const float2 xy[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};
    StateVertex out;out.position=float4(xy[index],.5,1);return out;
}
vertex StateVertex vs_state(uint index [[vertex_id]]) {return state_vertex(index);}
fragment float4 fs_state(StateVertex in [[stage_in]]) {return float4(.75,.125,.25,1);}
vertex StateVertex vs_near(uint index [[vertex_id]]) {StateVertex out=state_vertex(index);out.position.z=.25;return out;}
vertex StateVertex vs_far(uint index [[vertex_id]]) {StateVertex out=state_vertex(index);out.position.z=.75;return out;}
vertex StateVertex vs_half(uint index [[vertex_id]]) {StateVertex out=state_vertex(index);if(index==1)out.position.x=1;return out;}
fragment float4 fs_red(StateVertex in [[stage_in]]) {return float4(.25,.875,.5,1);}
fragment float4 fs_blend(StateVertex in [[stage_in]]) {return float4(.75,.125,.25,.25);}
struct MaskOutput {float4 color [[color(0)]]; uint mask [[sample_mask]];};
fragment MaskOutput fs_mask(StateVertex in [[stage_in]]) {MaskOutput out;out.color=float4(.75,.125,.25,1);out.mask=15;return out;}
struct MRT2 {float4 c0 [[color(0)]];float4 c1 [[color(1)]];};
fragment MRT2 fs_mrt2(StateVertex in [[stage_in]]) {MRT2 out;out.c0=float4(.75,.125,.25,1);out.c1=float4(.875,.75,.5,1);return out;}
struct MRT4 {float4 c0 [[color(0)]];float4 c1 [[color(1)]];float4 c2 [[color(2)]];float4 c3 [[color(3)]];};
fragment MRT4 fs_mrt4(StateVertex in [[stage_in]]) {MRT4 out;out.c0=float4(.75,.125,.25,1);out.c1=out.c2=out.c3=float4(.875,.75,.5,1);return out;}
struct MRT8 {float4 c0 [[color(0)]];float4 c1 [[color(1)]];float4 c2 [[color(2)]];float4 c3 [[color(3)]];float4 c4 [[color(4)]];float4 c5 [[color(5)]];float4 c6 [[color(6)]];float4 c7 [[color(7)]];};
fragment MRT8 fs_mrt8(StateVertex in [[stage_in]]) {MRT8 out;out.c0=float4(.75,.125,.25,1);out.c1=out.c2=out.c3=out.c4=out.c5=out.c6=out.c7=float4(.875,.75,.5,1);return out;}
