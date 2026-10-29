// SPDX-License-Identifier: MIT
#include "VideoPredictive.h"
#include <cassert>
#include <cstdint>
using namespace kepler::video;
static uint32_t get32(const PictureProposal& p, unsigned at) {
    return uint32_t(p.bytes[at]) | (uint32_t(p.bytes[at+1]) << 8) |
           (uint32_t(p.bytes[at+2]) << 16) | (uint32_t(p.bytes[at+3]) << 24);
}
int main() {
    ParsedBaselinePicture p; p.is_reference=true; p.slice_type=0; p.max_references=2;
    p.frame_num=1; p.poc_lsb=2; p.p_simple_reference_controls=true;
    p.picture.width=320; p.picture.height=240; p.picture.frame_mbs_only_flag=1;
    p.picture.slice_count=2; p.picture.log2_max_frame_num_minus4=1;
    p.picture.log2_max_pic_order_cnt_lsb_minus4=3; p.first_macroblocks={0,150};
    std::array<ReferenceState,17> slots{};
    slots[0].identity=10; slots[0].decoded_top=true; slots[0].decoded_bottom=true;
    slots[1].identity=11;
    std::array<PictureReference,2> refs{};
    refs[0].identity=10; refs[0].slot=0; refs[0].top=true; refs[0].bottom=true;
    PictureProposal out;
    assert(prepare_baseline_p(p,slots,refs,1,1,11,out));
    assert(out.caps==0x1113 && out.target_slot==1 && out.target_after.identity==11);
    assert(out.target_after.decoded_top && out.target_after.decoded_bottom);
    assert(get32(out,0x34)==((1u<<9)|(1u<<14)));
    assert(get32(out,0x38)==2 && get32(out,0x3c)==2);
    assert(get32(out,0x40)==(1u|(1u<<12)|(1u<<13)|(1u<<17)|(1u<<21)));
    assert(get32(out,0x4c)==0);
    for (unsigned i=0x140;i<0x220;i++) assert(out.bytes[i]==16);
    const auto saved=out;
    auto refuse=[&] { assert(!prepare_baseline_p(p,slots,refs,1,1,11,out));
        assert(out.bytes==saved.bytes && out.caps==saved.caps && out.target_after.identity==saved.target_after.identity); };
    p.p_simple_reference_controls=false; refuse(); p.p_simple_reference_controls=true;
    p.frame_gaps_allowed=true; refuse(); p.frame_gaps_allowed=false;
    p.poc_lsb=3; refuse(); p.poc_lsb=2;
    p.picture.weighted_pred_flag=1; refuse(); p.picture.weighted_pred_flag=0;
    p.first_macroblocks={0,0}; refuse(); p.first_macroblocks={0,150};
    refs[0].identity=12; refuse(); refs[0].identity=10;
    refs[0].long_term=true; refuse(); refs[0].long_term=false;
    slots[0].decoded_bottom=false; refuse(); slots[0].decoded_bottom=true;
    slots[1].decoded_top=true; refuse(); slots[1].decoded_top=false;
    assert(!prepare_baseline_p(p,slots,refs,1,0,10,out));
    assert(out.bytes==saved.bytes);
    // The caller supplies two chronological, previously completed references.
    p.frame_num=2; p.poc_lsb=4; slots[1].decoded_top=slots[1].decoded_bottom=true;
    slots[2].identity=12; refs[1].identity=11; refs[1].slot=1;
    refs[1].top=refs[1].bottom=true; refs[1].frame_index=1;
    refs[1].top_order=refs[1].bottom_order=2;
    assert(prepare_baseline_p(p,slots,refs,2,2,12,out));
    assert(get32(out,0x38)==4 && get32(out,0x5c)==1);
    refs[1].slot=0; assert(!prepare_baseline_p(p,slots,refs,2,2,12,out));
    // One-reference POC type 2: frame 2 references only frame 1.
    p.max_references=1; p.picture.pic_order_cnt_type=2; p.poc_lsb=0;
    std::array<ReferenceState,17> one{}; one[0].identity=13;
    one[1].identity=11; one[1].decoded_top=one[1].decoded_bottom=true;
    std::array<PictureReference,2> previous{}; previous[0].identity=11; previous[0].slot=1;
    previous[0].top=previous[0].bottom=true; previous[0].frame_index=1;
    previous[0].top_order=previous[0].bottom_order=2;
    assert(prepare_baseline_p(p,one,previous,1,0,13,out));
    assert(get32(out,0x38)==4 && get32(out,0x3c)==4 && get32(out,0x4c)==1);
    const auto single=out;
    p.poc_lsb=4; assert(!prepare_baseline_p(p,one,previous,1,0,13,out)); p.poc_lsb=0;
    previous[0].frame_index=0; assert(!prepare_baseline_p(p,one,previous,1,0,13,out)); previous[0].frame_index=1;
    p.frame_num=32; assert(!prepare_baseline_p(p,one,previous,1,0,13,out)); p.frame_num=2;
    assert(!prepare_baseline_p(p,one,previous,2,0,13,out));
    assert(out.bytes==single.bytes && out.target_after.identity==single.target_after.identity);
}
