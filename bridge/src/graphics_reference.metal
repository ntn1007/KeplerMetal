#include <metal_stdlib>
using namespace metal;
struct VertexOut {float4 position [[position]];};
vertex VertexOut vs_ref(uint index [[vertex_id]]) {
    const float2 positions[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};
    VertexOut out;out.position=float4(positions[index],0.5,1);return out;
}
fragment float4 fs_const(VertexOut in [[stage_in]]) {
    return float4(0.75,0.125,0.25,1);
}
fragment float4 fs_match(VertexOut in [[stage_in]]) {
    return float4(0.25,0.5,0.75,1);
}
fragment float4 fs_read(VertexOut in [[stage_in]],texture2d<float> image [[texture(0)]]) {
    return image.read(uint2(in.position.xy));
}
fragment float4 fs_nearest(VertexOut in [[stage_in]],texture2d<float> image [[texture(0)]],sampler s [[sampler(0)]]) {
    float2 size=float2(image.get_width(),image.get_height());
    return image.sample(s,in.position.xy/size);
}
fragment float4 fs_linear(VertexOut in [[stage_in]],texture2d<float> image [[texture(0)]],sampler s [[sampler(0)]]) {
    float2 size=float2(image.get_width(),image.get_height());
    return image.sample(s,(in.position.xy+float2(0.25,0.125))/size);
}
