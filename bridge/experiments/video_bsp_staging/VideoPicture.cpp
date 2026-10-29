// SPDX-License-Identifier: MIT
#include "VideoPicture.h"
#include "VideoLayout.h"
#include <algorithm>
#include <limits>

namespace kepler::video {
namespace {
void put16(std::array<uint8_t, 756>& b, size_t i, uint16_t v) {
    b[i] = uint8_t(v); b[i+1] = uint8_t(v >> 8);
}
void put32(std::array<uint8_t, 756>& b, size_t i, uint32_t v) {
    for (unsigned j = 0; j != 4; ++j) b[i+j] = uint8_t(v >> (8*j));
}
}
bool prepare_video_picture(const VideoPicture& v, PictureProposal& out) noexcept {
    const auto& p = v.picture;
    if (v.max_references > 16 || v.reference_count > v.max_references ||
        v.target_slot > v.max_references || !v.target_identity ||
        v.slots[v.target_slot].identity != v.target_identity ||
        p.log2_max_frame_num_minus4 > 12 || p.pic_order_cnt_type > 2 ||
        p.pic_init_qp_minus26 < -26 || p.pic_init_qp_minus26 > 25 ||
        v.chroma_qp_offset < -12 || v.chroma_qp_offset > 12 ||
        v.second_chroma_qp_offset < -12 || v.second_chroma_qp_offset > 12 ||
        p.mb_adaptive_frame_field_flag > 1 || p.direct_8x8_inference_flag > 1 ||
        p.weighted_pred_flag > 1 || p.weighted_bipred_idc > 2 ||
        p.field_pic_flag > 1 || p.bottom_field_flag > 1 ||
        (!p.field_pic_flag && p.bottom_field_flag)) return false;
    for (unsigned i = 0; i < v.reference_count; ++i) {
        const auto& ref = v.refs[i];
        if (ref.slot > v.max_references || !ref.identity || v.slots[ref.slot].identity != ref.identity)
            return false;
    }
    VideoLayout l;
    if (!plan_h264_layout(p.width, p.height, v.max_references, p.slice_count,
                          std::numeric_limits<uint64_t>::max(), l) ||
        !l.temporary_stride || (l.temporary_stride & 255)) return false;
    PictureProposal r;
    auto& b = r.bytes;
    const uint32_t width = (p.width + 15) / 16, height = (p.height + 15) / 16;
    put16(b, 0, uint16_t(width)); put16(b, 2, uint16_t(height));
    put32(b, 4, width*16); put32(b, 8, width*16);
    put32(b, 0x10, uint32_t(l.second_luma_offset/256));
    put32(b, 0x18, uint32_t(l.chroma_offset/256));
    put32(b, 0x1c, uint32_t(l.second_chroma_offset/256));
    put32(b, 0x20, uint32_t(l.chroma_offset/256));
    put32(b, 0x24, uint32_t(l.temporary_stride/256));
    put32(b, 0x28, l.bucket_units); put32(b, 0x2c, l.ring_units);
    auto after = v.slots[v.target_slot];
    bool second = false;
    if (!after.decoded_top && !after.decoded_bottom) after.decoded_first = p.bottom_field_flag;
    else second = after.decoded_first != bool(p.bottom_field_flag);
    uint32_t flags = uint32_t(p.mb_adaptive_frame_field_flag) |
        (uint32_t(p.direct_8x8_inference_flag)<<1) | (uint32_t(p.weighted_pred_flag)<<2) |
        (uint32_t(v.constrained_intra)<<3) | (uint32_t(v.is_reference)<<4) |
        (uint32_t(p.field_pic_flag)<<5) | (uint32_t(p.bottom_field_flag)<<6) |
        (uint32_t(second)<<7) | (uint32_t(p.log2_max_frame_num_minus4)<<8) | (1u<<12) |
        (uint32_t(p.pic_order_cnt_type)<<14) | ((uint32_t(p.pic_init_qp_minus26)&63u)<<16) |
        ((uint32_t(v.chroma_qp_offset)&31u)<<22) | ((uint32_t(v.second_chroma_qp_offset)&31u)<<27);
    put32(b, 0x30, flags);
    put32(b, 0x34, uint32_t(p.weighted_bipred_idc) | (uint32_t(v.target_slot)<<9) |
                       (uint32_t(v.frame_number)<<14));
    put32(b, 0x38, uint32_t(v.top_order)); put32(b, 0x3c, uint32_t(v.bottom_order));
    for (unsigned i = 0; i < v.reference_count; ++i) {
        const auto& ref = v.refs[i]; const auto& state = v.slots[ref.slot];
        const uint32_t top = state.decoded_top && ref.top ? 1u + uint32_t(ref.long_term) : 0;
        const uint32_t bottom = state.decoded_bottom && ref.bottom ? 1u + uint32_t(ref.long_term) : 0;
        const uint32_t word = (i+1) | (uint32_t(ref.slot)<<7) |
            (uint32_t(!state.field_picture && ref.top)<<12) |
            (uint32_t(!state.field_picture && ref.bottom)<<13) | (uint32_t(ref.long_term)<<14) |
            (uint32_t(state.field_picture)<<16) | (top<<17) | (bottom<<21);
        const size_t pos = 0x40 + 16*i;
        put32(b, pos, word); put32(b, pos+4, uint32_t(ref.top_order));
        put32(b, pos+8, uint32_t(ref.bottom_order)); put32(b, pos+12, ref.frame_index);
    }
    std::copy(v.scaling4.begin(), v.scaling4.end(), b.begin()+0x140);
    std::copy(v.scaling8.begin(), v.scaling8.end(), b.begin()+0x1a0);
    after.field_picture = p.field_pic_flag;
    if (!p.field_pic_flag || p.bottom_field_flag) after.decoded_bottom = true;
    if (!p.field_pic_flag || !p.bottom_field_flag) after.decoded_top = true;
    r.caps = 0x1113; r.target_slot = v.target_slot; r.target_after = after;
    out = r;
    return true;
}
}
