// SPDX-License-Identifier: MIT
#include "VideoPredictive.h"

namespace kepler::video {
bool prepare_baseline_p(const ParsedBaselinePicture& p,
                        const std::array<ReferenceState, 17>& slots,
                        const std::array<PictureReference, 2>& refs,
                        uint8_t count, uint8_t target, uint64_t identity,
                        PictureProposal& out) noexcept {
    const auto& pic = p.picture;
    if (p.is_idr || !p.is_reference || p.slice_type != 0 || p.max_references != 2 ||
        !p.p_simple_reference_controls || p.frame_gaps_allowed || p.delta_poc_bottom ||
        p.idr_no_output_prior || p.idr_long_term ||
        !p.frame_num || p.frame_num > 0xffff || pic.log2_max_frame_num_minus4 > 12 ||
        pic.log2_max_pic_order_cnt_lsb_minus4 > 12 || pic.pic_order_cnt_type ||
        pic.frame_mbs_only_flag != 1 || pic.field_pic_flag || pic.bottom_field_flag ||
        pic.entropy_coding_mode_flag || pic.weighted_pred_flag || pic.weighted_bipred_idc ||
        pic.num_ref_idx_l1_active_minus1 || !pic.width || !pic.height ||
        (pic.width & 15u) || (pic.height & 15u) || pic.num_ref_idx_l0_active_minus1 || p.first_macroblocks.empty() ||
        p.first_macroblocks.size() != pic.slice_count || p.first_macroblocks.front() != 0 ||
        target > 2 || !identity || slots[target].identity != identity ||
        slots[target].field_picture || slots[target].decoded_top || slots[target].decoded_bottom ||
        slots[target].decoded_first) return false;
    const uint64_t macros = uint64_t(pic.width / 16) * (pic.height / 16);
    for (size_t i = 0; i < p.first_macroblocks.size(); ++i)
        if (p.first_macroblocks[i] >= macros || (i && p.first_macroblocks[i] <= p.first_macroblocks[i-1])) return false;
    const uint32_t max_frame = 1u << (pic.log2_max_frame_num_minus4 + 4);
    const uint32_t max_poc = 1u << (pic.log2_max_pic_order_cnt_lsb_minus4 + 4);
    if (p.frame_num >= max_frame || p.frame_num > (max_poc - 1) / 2 ||
        p.poc_lsb != p.frame_num * 2 || count != (p.frame_num == 1 ? 1 : 2)) return false;
    for (uint8_t i = 0; i < count; ++i) {
        const auto& r = refs[i];
        if (r.slot > 2 || r.slot == target || !r.identity || r.identity == identity ||
            slots[r.slot].identity != r.identity || slots[r.slot].field_picture ||
            !slots[r.slot].decoded_top || !slots[r.slot].decoded_bottom || slots[r.slot].decoded_first ||
            !r.top || !r.bottom || r.long_term || r.frame_index != p.frame_num - count + i ||
            r.top_order != static_cast<int32_t>(r.frame_index * 2) || r.bottom_order != r.top_order ||
            (i && (r.slot == refs[0].slot || r.identity == refs[0].identity))) return false;
    }
    VideoPicture v;
    v.picture = pic; v.max_references = 2; v.reference_count = count;
    v.target_slot = target; v.target_identity = identity; v.slots = slots;
    v.is_reference = true; v.constrained_intra = p.constrained_intra;
    v.chroma_qp_offset = p.chroma_qp_offset; v.second_chroma_qp_offset = p.chroma_qp_offset;
    v.frame_number = static_cast<uint16_t>(p.frame_num);
    v.top_order = static_cast<int32_t>(p.poc_lsb); v.bottom_order = v.top_order;
    v.scaling4.fill(16); v.scaling8.fill(16);
    for (uint8_t i = 0; i < count; ++i) v.refs[i] = refs[i];
    return prepare_video_picture(v, out);
}
}
