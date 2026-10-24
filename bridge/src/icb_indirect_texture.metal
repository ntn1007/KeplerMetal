// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
struct ICBImageArguments {
    texture2d<float> image [[id(0)]];
    sampler sampling [[id(1)]];
    device const uint *input [[id(2)]];
};
struct ICBImageParameters { uint count,seed,trial,reserved; };
kernel void sample_icb_arguments(device ICBImageArguments &args [[buffer(0)]],
    device uint4 *output [[buffer(1)]],constant ICBImageParameters &p [[buffer(2)]],
    uint gid [[thread_position_in_grid]]) {
    if(gid>=p.count)return;
    int x=int((gid*3u+p.trial)%12u)-4,y=int((gid*5u+p.trial*2u)%12u)-4;
    float2 uv=(float2(x,y)+0.5f)*0.25f;
    uint4 texel=uint4(round(args.image.sample(args.sampling,uv)*255.0f));
    uint value=args.input[gid];
    uint shape=(args.image.get_width()<<16)|args.image.get_height();
    shape^=args.image.get_num_mip_levels()<<8;
    output[gid]=texel^uint4(value^p.seed,gid*3u,value*5u+p.trial,0xc0010000u^gid^shape);
}
