// SPDX-License-Identifier: MIT
// CPU-only comparison of candidate reference order/POC conventions. No GPU transport.
#include "VideoPicture.h"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
using namespace kepler::video;
extern "C" uint32_t mesa_vp_reference(const uint32_t*, const uint8_t*, uint8_t*, uint32_t*);
int main(int argc, char** argv) {
    if (argc != 4 || std::strlen(argv[1]) != 1 || std::strlen(argv[2]) != 1) return 2;
    const unsigned frame=unsigned(argv[1][0]-'0'), mode=unsigned(argv[2][0]-'0');
    if (frame<1 || frame>5 || mode>3) return 2;
    const bool recent_first=mode&1, offset_poc=mode&2;
    const unsigned count=frame==1?1:2, target=frame%3, offset=offset_poc?65536:0;
    VideoPicture v; auto& p=v.picture;
    p.width=320; p.height=240; p.slice_count=2; p.direct_8x8_inference_flag=1;
    p.log2_max_frame_num_minus4=1; p.pic_order_cnt_type=0; p.pic_init_qp_minus26=2;
    v.max_references=2; v.reference_count=count; v.target_slot=target; v.target_identity=target+1;
    v.slots[target].identity=target+1; v.is_reference=true; v.frame_number=frame;
    v.top_order=v.bottom_order=int32_t(2*frame+offset); v.scaling4.fill(16); v.scaling8.fill(16);
    uint32_t x[256]{}; x[0]=320; x[1]=240; x[2]=2; x[3]=2; x[4]=count; x[5]=target;
    x[6]=18; x[7]=1; x[8]=0; x[9]=2; x[13]=frame; x[14]=x[15]=2*frame+offset;
    for (unsigned i=0;i<count;++i) {
        const unsigned ref_frame=recent_first?frame-1-i:frame-count+i;
        const unsigned slot=ref_frame%3;
        v.slots[slot].identity=slot+1; v.slots[slot].decoded_top=v.slots[slot].decoded_bottom=true;
        auto& ref=v.refs[i]; ref.slot=slot; ref.identity=slot+1; ref.top=ref.bottom=true;
        ref.frame_index=ref_frame; ref.top_order=ref.bottom_order=int32_t(2*ref_frame+offset);
        x[32+slot]=6; auto *m=x+64+5*i; m[0]=slot; m[1]=3; m[2]=m[3]=2*ref_frame+offset; m[4]=ref_frame;
    }
    PictureProposal got; if (!prepare_video_picture(v,got)) return 3;
    alignas(4) uint8_t expected[756]{}; uint8_t scaling[224]; std::memset(scaling,16,sizeof scaling); uint32_t after=0;
    const auto caps=mesa_vp_reference(x,scaling,expected,&after);
    if (caps!=got.caps || after!=6 || std::memcmp(got.bytes.data(),expected,sizeof expected)) return 4;
    FILE *f=std::fopen(argv[3],"wb"); if (!f) return 5;
    const bool ok=std::fwrite(got.bytes.data(),1,got.bytes.size(),f)==got.bytes.size();
    return (!ok || std::fclose(f))?6:0;
}
