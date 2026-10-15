#include <metal_stdlib>
using namespace metal;
struct ResourceParameters {float4 scale;float4 bias;uint4 shape;};
static uint resource_index(uint3 id,constant ResourceParameters&p){return (id.z*p.shape.y+id.y)*p.shape.x+id.x;}
kernel void buffers_a(device const float4*input [[buffer(0)]],constant ResourceParameters&p [[buffer(3)]],device float4*output [[buffer(7)]],uint3 id [[thread_position_in_grid]]) {
    if(all(id<p.shape.xyz))output[resource_index(id,p)]=input[resource_index(id,p)]*p.scale+p.bias;
}
kernel void buffers_b(device const float4*input [[buffer(5)]],constant ResourceParameters&p [[buffer(11)]],device float4*output [[buffer(2)]],uint3 id [[thread_position_in_grid]]) {
    if(all(id<p.shape.xyz))output[resource_index(id,p)]=input[resource_index(id,p)]*p.scale+p.bias;
}
kernel void buffers_rw(device float4*input [[buffer(0)]],constant ResourceParameters&p [[buffer(3)]],device float4*output [[buffer(7)]],uint3 id [[thread_position_in_grid]]) {
    if(all(id<p.shape.xyz)){uint i=resource_index(id,p);float4 value=input[i];input[i]=value+1;output[i]=value*p.scale+p.bias;}
}
kernel void image_store(texture2d<float,access::write>image [[texture(0)]],uint2 id [[thread_position_in_grid]]) {
    if(id.x<image.get_width()&&id.y<image.get_height())image.write(float4(float(id.x)/64,float(id.y)/48,.25,1),id);
}
