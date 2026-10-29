// SPDX-License-Identifier: MIT
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace kepler::video {

struct ByteChunk {
    const uint8_t* data;
    size_t size;
};

// Values are supplied by a future H.264 parser; this structure does not
// validate a bitstream or establish support for any H.264 profile.
struct H264Picture {
    uint32_t width, height, slice_count;
    uint8_t log2_max_frame_num_minus4, pic_order_cnt_type, log2_max_pic_order_cnt_lsb_minus4;
    uint8_t delta_pic_order_always_zero_flag, frame_mbs_only_flag, direct_8x8_inference_flag;
    uint8_t entropy_coding_mode_flag, bottom_field_pic_order_in_frame_present_flag;
    uint8_t num_ref_idx_l0_active_minus1, num_ref_idx_l1_active_minus1;
    uint8_t weighted_pred_flag, weighted_bipred_idc;
    int8_t pic_init_qp_minus26;
    uint8_t deblocking_filter_control_present_flag, redundant_pic_cnt_present_flag;
    uint8_t transform_8x8_mode_flag, mb_adaptive_frame_field_flag;
    uint8_t field_pic_flag, bottom_field_flag;
};

// CPU-only stream staging. The returned bytes contain no qualified picture
// descriptor, GPU addresses, channel commands, or submission capability.
enum class StagingStatus { ok, invalid_input, too_large, allocation_failed };
StagingStatus stage_h264_stream(const ByteChunk* chunks, size_t count,
                                std::vector<uint8_t>& out) noexcept;

// Adds the Mesa-derived BSP picture block to the staged stream. On failure,
// both outputs remain unchanged. The result is still not GPU-submittable.
StagingStatus prepare_h264_bsp_picture(const H264Picture& picture,
                                      const ByteChunk* chunks, size_t count,
                                      std::vector<uint8_t>& out,
                                      uint32_t& bsp_flags) noexcept;

} // namespace kepler::video
