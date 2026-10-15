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

// Resource operations follow the native reference above, grouped into a
// fragment argument buffer as required by the ICB resource interface.
struct FragmentParameters {float4 scale;float4 bias;};
struct FragmentArguments {
    texture2d<float> image [[id(0)]];
    sampler s [[id(1)]];
    device const FragmentParameters *parameters [[id(2)]];
};
fragment float4 fs_arg_read(VertexOut in [[stage_in]],constant FragmentArguments &a [[buffer(0)]]) {
    return a.image.read(uint2(in.position.xy))*a.parameters->scale+a.parameters->bias;
}
fragment float4 fs_arg_nearest(VertexOut in [[stage_in]],constant FragmentArguments &a [[buffer(0)]]) {
    float2 size=float2(a.image.get_width(),a.image.get_height());
    return a.image.sample(a.s,in.position.xy/size)*a.parameters->scale+a.parameters->bias;
}
fragment float4 fs_arg_linear(VertexOut in [[stage_in]],constant FragmentArguments &a [[buffer(0)]]) {
    float2 size=float2(a.image.get_width(),a.image.get_height());
    return a.image.sample(a.s,(in.position.xy+float2(0.25,0.125))/size)*a.parameters->scale+a.parameters->bias;
}
