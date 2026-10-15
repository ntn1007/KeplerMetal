#include <metal_stdlib>
using namespace metal;
struct ImageLoadParameters {float4 scale;float4 bias;uint4 shape;};
// Allocate the installed driver's surface descriptor through its normal write
// interface. The controlled fixture never selects the write branch.
kernel void surface_load_carrier(texture2d<float,access::write>image [[texture(0)]],
                                 device float4 *output [[buffer(7)]],
                                 device uint4 *rawOutput [[buffer(8)]],
                                 constant ImageLoadParameters &p [[buffer(3)]],
                                 uint2 id [[thread_position_in_grid]]) {
    if(all(id<p.shape.xy)) {
        output[id.y*p.shape.x+id.x]=float4(.25,.5,.75,1)+p.bias;
        rawOutput[id.y*p.shape.x+id.x]=uint4(0x1234,0x5678,0xabcd,0xeffe);
        if(p.shape.x==0x12345678u)image.write(p.scale,id);
    }
}
kernel void image_read_reference(texture2d<float,access::read>image [[texture(0)]],
                                 device float4 *output [[buffer(7)]],
                                 constant ImageLoadParameters &p [[buffer(3)]],
                                 uint2 id [[thread_position_in_grid]]) {
    if(all(id<p.shape.xy)) {
        int2 xy=int2(id)+int2(p.shape.zw);
        bool inside=all(xy>=0)&&uint(xy.x)<image.get_width()&&uint(xy.y)<image.get_height();
        float4 value=inside?image.read(uint2(xy)):float4(0);
        output[id.y*p.shape.x+id.x]=value*p.scale+p.bias;
    }
}
