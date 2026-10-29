// SPDX-License-Identifier: MIT
#include "H264Baseline.h"
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>

static bool load(const char* path, std::vector<uint8_t>& bytes) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    if (!input) return false;
    const auto size = input.tellg();
    if (size <= 0 || size > 0x00ffffef) return false;
    input.seekg(0);
    bytes.resize(static_cast<size_t>(size));
    return static_cast<bool>(input.read(reinterpret_cast<char*>(bytes.data()), bytes.size()));
}

int main(int argc, char** argv) {
    if (argc != 5) return 2;
    std::vector<uint8_t> sps, pps, sample;
    if (!load(argv[1], sps) || !load(argv[2], pps) || !load(argv[3], sample)) return 3;
    kepler::video::ParsedBaselinePicture result;
    if (!kepler::video::parse_baseline_picture(sps.data(), sps.size(), pps.data(), pps.size(),
                                              sample.data(), sample.size(), result)) return 4;
    const kepler::video::ByteChunk chunk{result.annex_b.data(), result.annex_b.size()};
    std::vector<uint8_t> staged;
    uint32_t flags = 0;
    if (kepler::video::prepare_h264_bsp_picture(result.picture, &chunk, 1, staged, flags) !=
        kepler::video::StagingStatus::ok) return 5;
    std::ofstream file(argv[4], std::ios::binary | std::ios::trunc);
    if (!file || !file.write(reinterpret_cast<const char*>(staged.data()), staged.size())) return 6;
    const auto& p = result.picture;
    std::printf("{\"width\":%u,\"height\":%u,\"slice_count\":%u,\"frame_num\":%u,\"poc_lsb\":%u,"
                "\"slice_type\":%u,\"pps_id\":%u,\"flags\":%u,\"frame_log\":%u,\"poc_log\":%u,"
                "\"frame_mbs_only\":%u,\"direct_8x8\":%u,\"entropy\":%u,\"bottom_poc\":%u,"
                "\"l0\":%u,\"l1\":%u,\"weighted\":%u,\"bipred\":%u,\"qp\":%d,\"deblock\":%u,"
                "\"redundant\":%u,\"first_macroblocks\":[",
                p.width, p.height, p.slice_count, result.frame_num, result.poc_lsb, result.slice_type,
                result.pps_id, flags, p.log2_max_frame_num_minus4, p.log2_max_pic_order_cnt_lsb_minus4,
                p.frame_mbs_only_flag, p.direct_8x8_inference_flag, p.entropy_coding_mode_flag,
                p.bottom_field_pic_order_in_frame_present_flag, p.num_ref_idx_l0_active_minus1,
                p.num_ref_idx_l1_active_minus1, p.weighted_pred_flag, p.weighted_bipred_idc,
                static_cast<int>(p.pic_init_qp_minus26), p.deblocking_filter_control_present_flag,
                p.redundant_pic_cnt_present_flag);
    for (size_t i = 0; i < result.first_macroblocks.size(); ++i)
        std::printf("%s%u", i ? "," : "", result.first_macroblocks[i]);
    std::puts("]}");
    return 0;
}
