// SPDX-License-Identifier: MIT
#include "VideoIdr.h"
#include <cassert>
using namespace kepler::video;
int main() {
    ParsedBaselinePicture p; p.is_idr=true; p.is_reference=true; p.slice_type=2; p.max_references=2;
    p.picture.width=320; p.picture.height=240; p.picture.slice_count=2; p.picture.frame_mbs_only_flag=1;
    p.first_macroblocks={0,150}; p.chroma_qp_offset=-4; p.constrained_intra=true;
    PictureProposal out;
    assert(prepare_baseline_idr(p, 1, 77, out));
    assert(out.caps==0x1113 && out.target_slot==1 && out.target_after.identity==77);
    assert(out.target_after.decoded_top && out.target_after.decoded_bottom);
    for (unsigned i=0x140;i<0x220;i++) assert(out.bytes[i]==16);
    const auto saved=out;
    auto refuse=[&] {
        assert(!prepare_baseline_idr(p,1,77,out));
        assert(out.bytes==saved.bytes && out.caps==saved.caps && out.target_after.identity==saved.target_after.identity);
    };
    p.is_idr=false; refuse(); p.is_idr=true;
    p.is_reference=false; refuse(); p.is_reference=true;
    p.idr_long_term=true; refuse(); p.idr_long_term=false;
    p.idr_no_output_prior=true; refuse(); p.idr_no_output_prior=false;
    p.delta_poc_bottom=1; refuse(); p.delta_poc_bottom=0;
    p.poc_lsb=1; refuse(); p.poc_lsb=0;
    p.frame_num=1; refuse(); p.frame_num=0;
    p.first_macroblocks.pop_back(); refuse();
    assert(!prepare_baseline_idr(p,17,77,out));
}
