// SPDX-License-Identifier: MIT
#include "H264Stream.h"

#include <cstring>
#include <new>

namespace kepler::video {
namespace {
constexpr size_t kStreamOffset = 0x700;
constexpr size_t kTrailerSize = 16;
// Mesa documents the stream length as a 24-bit field. This conservative bound
// includes the trailer and is not a claim about macOS or hardware limits.
constexpr size_t kMaxStreamLength = 0x00ffffff;

void write_le32(std::vector<uint8_t>& bytes, size_t offset, uint32_t value) {
    for (unsigned i = 0; i != 4; ++i)
        bytes[offset + i] = static_cast<uint8_t>(value >> (8 * i));
}
} // namespace

StagingStatus stage_h264_stream(const ByteChunk* chunks, size_t count,
                                std::vector<uint8_t>& out) noexcept {
    if (count && !chunks) return StagingStatus::invalid_input;
    size_t total = 0;
    for (size_t i = 0; i < count; ++i) {
        if (chunks[i].size && !chunks[i].data) return StagingStatus::invalid_input;
        if (chunks[i].size > kMaxStreamLength - kTrailerSize - total)
            return StagingStatus::too_large;
        total += chunks[i].size;
    }
    try {
        std::vector<uint8_t> staged(kStreamOffset + total + kTrailerSize, 0);
        write_le32(staged, 0x100, static_cast<uint32_t>(total + kTrailerSize));
        write_le32(staged, 0x110, 1);
        size_t offset = kStreamOffset;
        for (size_t i = 0; i < count; ++i) {
            if (chunks[i].size) {
                std::memcpy(staged.data() + offset, chunks[i].data, chunks[i].size);
                offset += chunks[i].size;
            }
        }
        write_le32(staged, offset, 0x0b010000);
        write_le32(staged, offset + 8, 0x0b010000);
        out.swap(staged);
        return StagingStatus::ok;
    } catch (const std::bad_alloc&) {
        return StagingStatus::allocation_failed;
    }
}

StagingStatus prepare_h264_bsp_picture(const H264Picture& p,
                                      const ByteChunk* chunks, size_t count,
                                      std::vector<uint8_t>& out,
                                      uint32_t& bsp_flags) noexcept {
    // Project bounds prevent arithmetic overflow; they are not hardware caps.
    if (!p.width || !p.height || p.width > 65535 || p.height > 65535 ||
        !p.slice_count || p.slice_count > 0xfff || p.pic_order_cnt_type > 2 ||
        p.weighted_bipred_idc > 2) return StagingStatus::invalid_input;
    const uint8_t flags[] = {p.delta_pic_order_always_zero_flag, p.frame_mbs_only_flag,
        p.direct_8x8_inference_flag, p.entropy_coding_mode_flag,
        p.bottom_field_pic_order_in_frame_present_flag, p.weighted_pred_flag,
        p.deblocking_filter_control_present_flag, p.redundant_pic_cnt_present_flag,
        p.transform_8x8_mode_flag, p.mb_adaptive_frame_field_flag,
        p.field_pic_flag, p.bottom_field_flag};
    for (uint8_t flag : flags) if (flag > 1) return StagingStatus::invalid_input;

    std::vector<uint8_t> staged;
    const auto status = stage_h264_stream(chunks, count, staged);
    if (status != StagingStatus::ok) return status;
    const uint32_t fields[] = {
        1, p.log2_max_frame_num_minus4, p.pic_order_cnt_type,
        p.log2_max_pic_order_cnt_lsb_minus4, p.delta_pic_order_always_zero_flag,
        p.frame_mbs_only_flag, p.direct_8x8_inference_flag,
        (p.width + 15) / 16, (p.height + 15) / 16,
        p.entropy_coding_mode_flag, p.bottom_field_pic_order_in_frame_present_flag,
        0, 0, 0, p.num_ref_idx_l0_active_minus1, p.num_ref_idx_l1_active_minus1,
        p.weighted_pred_flag, p.weighted_bipred_idc,
        static_cast<uint32_t>(static_cast<int32_t>(p.pic_init_qp_minus26)),
        p.deblocking_filter_control_present_flag, p.redundant_pic_cnt_present_flag,
        p.transform_8x8_mode_flag, p.mb_adaptive_frame_field_flag
    };
    for (size_t i = 0; i < sizeof(fields) / sizeof(fields[0]); ++i)
        write_le32(staged, 4 * i, fields[i]);
    staged[0x5c] = p.field_pic_flag;
    staged[0x5d] = p.bottom_field_flag;
    const uint32_t flags_out = ((p.slice_count << 4) & 0xfff0u) | 3u | (1u << 17);
    out.swap(staged);
    bsp_flags = flags_out;
    return StagingStatus::ok;
}
} // namespace kepler::video
