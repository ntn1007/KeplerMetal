#include <metal_stdlib>
using namespace metal;
struct StateVertex {float4 position [[position]];};
vertex StateVertex vs_state(uint index [[vertex_id]]) {const float2 xy[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};StateVertex v;v.position=float4(xy[index],.5,1);return v;}
fragment float4 fs_state(StateVertex in [[stage_in]]) {return float4(.25,.125,.25,1);}
