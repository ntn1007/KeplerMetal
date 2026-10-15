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
