// SPDX-License-Identifier: MIT
#include "VideoPicture.h"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
using namespace kepler::video;
extern "C" uint32_t mesa_vp_reference(const uint32_t*, const uint8_t*, uint8_t*, uint32_t*);

static uint32_t state = 0x812394abu;
static uint32_t random_word() { state ^= state<<13; state ^= state>>17; state ^= state<<5; return state; }
int main() {
    for (unsigned n=0; n<4096; ++n) {
        uint32_t x[256]{}; uint8_t scaling[224];
        x[0]=16+random_word()%1920; x[1]=16+random_word()%1080; x[2]=1+random_word()%128;
        x[3]=random_word()%17; x[4]=random_word()%(x[3]+1); x[5]=random_word()%(x[3]+1);
        x[6]=random_word()%128; if (!(x[6]&32)) x[6]&=~64u;
        x[7]=random_word()%13; x[8]=random_word()%3; x[9]=uint32_t(int(random_word()%52)-26);
        x[10]=uint32_t(int(random_word()%25)-12); x[11]=uint32_t(int(random_word()%25)-12);
        x[12]=random_word()%3; x[13]=random_word()%65536; x[14]=random_word(); x[15]=random_word();
        VideoPicture v; auto& p=v.picture;
        p.width=x[0]; p.height=x[1]; p.slice_count=x[2];
        v.max_references=x[3]; v.reference_count=x[4]; v.target_slot=x[5];
        p.mb_adaptive_frame_field_flag=!!(x[6]&1); p.direct_8x8_inference_flag=!!(x[6]&2);
        p.weighted_pred_flag=!!(x[6]&4); v.constrained_intra=!!(x[6]&8); v.is_reference=!!(x[6]&16);
        p.field_pic_flag=!!(x[6]&32); p.bottom_field_flag=!!(x[6]&64);
        p.log2_max_frame_num_minus4=x[7]; p.pic_order_cnt_type=x[8]; p.pic_init_qp_minus26=int32_t(x[9]);
        v.chroma_qp_offset=int32_t(x[10]); v.second_chroma_qp_offset=int32_t(x[11]);
        p.weighted_bipred_idc=x[12]; v.frame_number=x[13]; v.top_order=int32_t(x[14]); v.bottom_order=int32_t(x[15]);
        for (unsigned i=0;i<17;++i) {
            x[32+i]=random_word()%16; auto& s=v.slots[i]; s.identity=i+1;
            s.field_picture=!!(x[32+i]&1); s.decoded_top=!!(x[32+i]&2);
            s.decoded_bottom=!!(x[32+i]&4); s.decoded_first=!!(x[32+i]&8);
        }
        v.target_identity=v.target_slot+1;
        for (unsigned i=0;i<v.reference_count;++i) {
            auto* r=x+64+5*i; r[0]=random_word()%(x[3]+1); r[1]=random_word()%8;
            r[2]=random_word(); r[3]=random_word(); r[4]=random_word();
            auto& d=v.refs[i]; d.slot=r[0]; d.identity=d.slot+1; d.top=!!(r[1]&1);
            d.bottom=!!(r[1]&2); d.long_term=!!(r[1]&4);
            d.top_order=int32_t(r[2]); d.bottom_order=int32_t(r[3]); d.frame_index=r[4];
        }
        for (auto& s:scaling) s=uint8_t(random_word());
        std::memcpy(v.scaling4.data(),scaling,96); std::memcpy(v.scaling8.data(),scaling+96,128);
        PictureProposal got; assert(prepare_video_picture(v,got));
        alignas(4) uint8_t expected[756]{}; uint32_t after=0;
        const auto caps=mesa_vp_reference(x,scaling,expected,&after);
        if (got.caps!=caps || std::memcmp(got.bytes.data(),expected,sizeof expected) ||
            got.target_after.field_picture != bool(after&1) || got.target_after.decoded_top != bool(after&2) ||
            got.target_after.decoded_bottom != bool(after&4) || got.target_after.decoded_first != bool(after&8)) {
            for (unsigned i=0;i<sizeof expected;++i) if (got.bytes[i]!=expected[i]) {
                std::fprintf(stderr,"case %u offset %x got %02x expected %02x\n",n,i,got.bytes[i],expected[i]); break;
            }
            return 1;
        }
    }
    VideoPicture bad; PictureProposal prior; prior.caps=42; prior.bytes.fill(37);
    prior.target_slot=4; prior.target_after.identity=123; prior.target_after.decoded_top=true;
    const PictureProposal saved=prior;
    const auto refused=[&] {
        assert(!prepare_video_picture(bad,prior));
        assert(prior.bytes==saved.bytes && prior.caps==saved.caps && prior.target_slot==saved.target_slot &&
               prior.target_after.identity==saved.target_after.identity &&
               prior.target_after.decoded_top==saved.target_after.decoded_top);
    };
    refused();
    bad.picture.width=320; bad.picture.height=240; bad.picture.slice_count=2;
    bad.target_identity=1; bad.slots[0].identity=2;
    refused();
    bad.slots[0].identity=1; bad.max_references=1; bad.reference_count=1;
    bad.refs[0].identity=2; bad.refs[0].slot=1; bad.slots[1].identity=3;
    refused();
    bad.slots[1].identity=2; bad.picture.bottom_field_flag=1; refused();
    bad.picture.bottom_field_flag=0; bad.picture.log2_max_frame_num_minus4=13; refused();
    bad.picture.log2_max_frame_num_minus4=0; bad.chroma_qp_offset=13; refused();
    bad.chroma_qp_offset=0; bad.reference_count=2; refused();
    bad.reference_count=1; bad.target_slot=17; refused();
    std::puts("PASS: 4096 Mesa VP picture blocks and state proposals; invalid identities refused");
}
