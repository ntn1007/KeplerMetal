// SPDX-License-Identifier: MIT
#include "VideoIdr.h"

namespace kepler::video {
bool prepare_baseline_idr(const ParsedBaselinePicture& p, uint8_t slot,
                          uint64_t identity, PictureProposal& out) noexcept {
    if (!p.is_idr || !p.is_reference || p.slice_type != 2 || p.frame_num || p.poc_lsb ||
        p.delta_poc_bottom || p.idr_no_output_prior || p.idr_long_term || !p.max_references ||
        p.max_references > 16 || slot > p.max_references || !identity ||
        p.picture.pic_order_cnt_type || p.picture.frame_mbs_only_flag != 1 ||
        p.picture.field_pic_flag || p.picture.bottom_field_flag ||
        p.first_macroblocks.size() != p.picture.slice_count || p.first_macroblocks.empty() ||
        p.first_macroblocks.front() != 0) return false;
    VideoPicture v;
    v.picture = p.picture; v.max_references = static_cast<uint8_t>(p.max_references);
    v.target_slot = slot; v.target_identity = identity; v.slots[slot].identity = identity;
    v.is_reference = true; v.constrained_intra = p.constrained_intra;
    v.chroma_qp_offset = p.chroma_qp_offset; v.second_chroma_qp_offset = p.chroma_qp_offset;
    // Baseline SPS and the accepted PPS have no scaling-matrix syntax.
    v.scaling4.fill(16); v.scaling8.fill(16);
    return prepare_video_picture(v, out);
}
}
