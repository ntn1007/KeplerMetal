// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
struct ResourceArguments {
    texture2d<float> image [[id(0)]];
    sampler sampling [[id(1)]];
    device const uint *input [[id(2)]];
};
kernel void consume_native_resource_ids(device ResourceArguments &args [[buffer(0)]],
    device uint4 *output [[buffer(1)]],constant uint4 &meta [[buffer(2)]],
    uint gid [[thread_position_in_grid]]) {
    if(gid>=meta.x)return;
    int x=int((gid*3u+meta.z)%12u)-4,y=int((gid*5u+meta.z*2u)%12u)-4;
    float2 uv=(float2(x,y)+0.5f)*0.25f;
    uint4 texel=uint4(round(args.image.sample(args.sampling,uv)*255.0f));
    uint value=args.input[gid];
    uint shape=(args.image.get_width()<<16)|args.image.get_height();
    shape^=args.image.get_num_mip_levels()<<8;
    output[gid]=texel^uint4(value^meta.y,gid*3u,value*5u+meta.z,0xc0010000u^gid^shape);
}
