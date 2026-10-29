// SPDX-License-Identifier: MIT
#include "H264Stream.h"
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

extern "C" uint32_t mesa_reference_picture(const uint32_t* values, unsigned char* out);
using namespace kepler::video;

static uint32_t next(uint32_t& state) {
    state ^= state << 13; state ^= state >> 17; state ^= state << 5; return state;
}

int main() {
    uint32_t seed = 0x5a3e14b7;
    const uint8_t payload[] = {0, 0, 1, 0x65, 0x12};
    const ByteChunk chunk{payload, sizeof(payload)};
    for (unsigned iteration = 0; iteration < 4096; ++iteration) {
        H264Picture p{};
        p.width = 1 + next(seed) % 65535; p.height = 1 + next(seed) % 65535;
        p.slice_count = 1 + next(seed) % 4095;
        p.log2_max_frame_num_minus4 = next(seed) % 13; p.pic_order_cnt_type = next(seed) % 3;
        p.log2_max_pic_order_cnt_lsb_minus4 = next(seed) % 13;
        p.delta_pic_order_always_zero_flag = next(seed) % 2; p.frame_mbs_only_flag = next(seed) % 2;
        p.direct_8x8_inference_flag = next(seed) % 2; p.entropy_coding_mode_flag = next(seed) % 2;
        p.bottom_field_pic_order_in_frame_present_flag = next(seed) % 2;
        p.num_ref_idx_l0_active_minus1 = next(seed) % 32; p.num_ref_idx_l1_active_minus1 = next(seed) % 32;
        p.weighted_pred_flag = next(seed) % 2; p.weighted_bipred_idc = next(seed) % 3;
        p.pic_init_qp_minus26 = static_cast<int8_t>(static_cast<int>(next(seed) % 52) - 26);
        p.deblocking_filter_control_present_flag = next(seed) % 2;
        p.redundant_pic_cnt_present_flag = next(seed) % 2; p.transform_8x8_mode_flag = next(seed) % 2;
        p.mb_adaptive_frame_field_flag = next(seed) % 2; p.field_pic_flag = next(seed) % 2;
        p.bottom_field_flag = next(seed) % 2;
        if (iteration == 0) { p.width = 65535; p.height = 1; p.slice_count = 4095; p.pic_init_qp_minus26 = -26; }
        if (iteration == 1) { p.width = 1; p.height = 65535; p.slice_count = 1; p.pic_init_qp_minus26 = 25; }
        const uint32_t x[] = {p.width, p.height, p.slice_count, p.log2_max_frame_num_minus4,
            p.pic_order_cnt_type, p.log2_max_pic_order_cnt_lsb_minus4,
            p.delta_pic_order_always_zero_flag, p.frame_mbs_only_flag, p.direct_8x8_inference_flag,
            p.entropy_coding_mode_flag, p.bottom_field_pic_order_in_frame_present_flag,
            p.num_ref_idx_l0_active_minus1, p.num_ref_idx_l1_active_minus1, p.weighted_pred_flag,
            p.weighted_bipred_idc, static_cast<uint32_t>(static_cast<int32_t>(p.pic_init_qp_minus26)),
            p.deblocking_filter_control_present_flag, p.redundant_pic_cnt_present_flag,
            p.transform_8x8_mode_flag, p.mb_adaptive_frame_field_flag, p.field_pic_flag, p.bottom_field_flag};
        alignas(uint32_t) unsigned char reference[128]{};
        const uint32_t expected = mesa_reference_picture(x, reference) | (1u << 17);
        std::vector<uint8_t> output;
        uint32_t result = 0;
        assert(prepare_h264_bsp_picture(p, &chunk, 1, output, result) == StagingStatus::ok);
        assert(result == expected && std::equal(reference, reference + 124, output.begin()));
        assert(std::equal(payload, payload + sizeof(payload), output.begin() + 0x700));
    }
    H264Picture invalid{};
    std::vector<uint8_t> output{3, 1, 4};
    const auto saved = output;
    uint32_t flags = 0xabcdef01;
    auto rejected = [&] {
        assert(prepare_h264_bsp_picture(invalid, &chunk, 1, output, flags) == StagingStatus::invalid_input);
        assert(output == saved && flags == 0xabcdef01);
    };
    rejected();
    invalid.width = 320; invalid.height = 240; invalid.slice_count = 4096; rejected();
    invalid.slice_count = 1; invalid.field_pic_flag = 2; rejected();
    invalid.field_pic_flag = 0; invalid.weighted_bipred_idc = 3; rejected();
    invalid.weighted_bipred_idc = 0; invalid.pic_order_cnt_type = 3; rejected();
    invalid.pic_order_cnt_type = 0; invalid.width = 65536; rejected();
    invalid.width = 320;
    const ByteChunk missing{nullptr, 1};
    assert(prepare_h264_bsp_picture(invalid, &missing, 1, output, flags) == StagingStatus::invalid_input);
    assert(output == saved && flags == 0xabcdef01);
    const ByteChunk too_large{payload, 0x00ffffff};
    assert(prepare_h264_bsp_picture(invalid, &too_large, 1, output, flags) == StagingStatus::too_large);
    assert(output == saved && flags == 0xabcdef01);
    std::puts("PASS: 4096 Mesa picture blocks and flags; invalid inputs refused");
}
