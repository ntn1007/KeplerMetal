// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
struct Input {float4 position [[attribute(0)]];float4 color [[attribute(1)]];float4 offset [[attribute(2)]];};
struct Smooth {float4 position [[position]];float4 color [[user(locn0)]];};
struct Flat {float4 position [[position]];float4 color [[user(locn0),flat]];};
static float4 position(Input in){float4 p=in.position;p.xy+=in.offset.xy*p.w;return p;}
static float4 color(Input in,uint instance){float4 c=in.color;c.z+=float(instance)/64.f+in.offset.z;return c;}
vertex Smooth vs_quad_smooth(Input in [[stage_in]],uint instance [[instance_id]]) {Smooth out;out.position=position(in);out.color=color(in,instance);return out;}
vertex Flat vs_quad_flat(Input in [[stage_in]],uint instance [[instance_id]]) {Flat out;out.position=position(in);out.color=color(in,instance);return out;}
struct FragmentParameters {float4 scale;float4 bias;};
struct FragmentArguments {texture2d<float> image [[id(0)]];sampler s [[id(1)]];device const FragmentParameters *parameters [[id(2)]];};
fragment float4 fs_quad_smooth(Smooth in [[stage_in]],constant FragmentArguments&a [[buffer(0)]]) {return in.color*(a.image.read(uint2(in.position.xy))*a.parameters->scale+a.parameters->bias);}
fragment float4 fs_quad_flat(Flat in [[stage_in]],constant FragmentArguments&a [[buffer(0)]]) {return in.color*(a.image.read(uint2(in.position.xy))*a.parameters->scale+a.parameters->bias);}
