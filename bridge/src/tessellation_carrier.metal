#include <metal_stdlib>
using namespace metal;
struct TessOut {float4 position [[position]];float4 color [[user(locn0)]];};
[[patch(triangle,3)]]
vertex TessOut tess_triangle(float3 coord [[position_in_patch]]) {
    TessOut out;
    out.position=float4(-coord.x+3*coord.y-coord.z,-coord.x-coord.y+3*coord.z,.5,1);
    out.color=float4(coord*coord,1);
    return out;
}
fragment float4 tess_fragment(TessOut in [[stage_in]]) {return in.color;}
