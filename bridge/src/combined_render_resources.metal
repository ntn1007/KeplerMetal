#include <metal_stdlib>
using namespace metal;
struct IOInput {
    float4 position [[attribute(0)]];
    float4 color [[attribute(1)]];
    float4 offset [[attribute(2)]];
};
struct SmoothOut {float4 position [[position]];float4 color [[user(locn0)]];};
struct LinearOut {float4 position [[position]];float4 color [[user(locn0),center_no_perspective]];};
struct FlatOut {float4 position [[position]];float4 color [[user(locn0),flat]];};
static float4 io_position(IOInput in){float4 p=in.position;p.xy+=in.offset.xy*p.w;return p;}
static float4 io_color(IOInput in,uint instance){float4 c=in.color;c.z+=float(instance)/64.0+in.offset.z;return c;}
vertex SmoothOut vs_io_smooth(IOInput in [[stage_in]],uint instance [[instance_id]]) {SmoothOut out;out.position=io_position(in);out.color=io_color(in,instance);return out;}
vertex LinearOut vs_io_linear(IOInput in [[stage_in]],uint instance [[instance_id]]) {LinearOut out;out.position=io_position(in);out.color=io_color(in,instance);return out;}
vertex FlatOut vs_io_flat(IOInput in [[stage_in]],uint instance [[instance_id]]) {FlatOut out;out.position=io_position(in);out.color=io_color(in,instance);return out;}
fragment float4 fs_io_smooth(SmoothOut in [[stage_in]]) {return in.color;}
fragment float4 fs_io_linear(LinearOut in [[stage_in]]) {return in.color;}
fragment float4 fs_io_flat(FlatOut in [[stage_in]]) {return in.color;}
struct IndirectParameters {ulong addresses[4];uint grid[3];uint block[3];};
// Negative control: safely produces an empty draw if this carrier runs unchanged.
kernel void write_draw_arguments(constant IndirectParameters&p [[buffer(0)]],device uint*out [[buffer(1)]],uint index [[thread_position_in_grid]]) {
    if(index<p.grid[0])out[index]=0;
}

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

fragment float4 fs_combined_smooth(SmoothOut in [[stage_in]],constant FragmentArguments &a [[buffer(0)]]) {return (a.image.read(uint2(in.position.xy)))*in.color*a.parameters->scale+a.parameters->bias;}

fragment float4 fs_combined_linear(LinearOut in [[stage_in]],constant FragmentArguments &a [[buffer(0)]]) {return (a.image.sample(a.s,(in.position.xy+float2(0.25,0.125))/float2(a.image.get_width(),a.image.get_height())))*in.color*a.parameters->scale+a.parameters->bias;}

fragment float4 fs_combined_flat(FlatOut in [[stage_in]],constant FragmentArguments &a [[buffer(0)]]) {return (a.image.sample(a.s,in.position.xy/float2(a.image.get_width(),a.image.get_height())))*in.color*a.parameters->scale+a.parameters->bias;}
