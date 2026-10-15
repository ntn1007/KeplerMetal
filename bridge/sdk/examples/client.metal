#include <metal_stdlib>
using namespace metal;
struct ClientVertex {float4 position [[position]];};
vertex ClientVertex client_vertex(uint i [[vertex_id]]) {
    const float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};
    ClientVertex v;v.position=float4(p[i],.5,1);return v;
}
fragment float4 client_fragment(ClientVertex v [[stage_in]]) {
    return float4(.375,.625,.875,1);
}
