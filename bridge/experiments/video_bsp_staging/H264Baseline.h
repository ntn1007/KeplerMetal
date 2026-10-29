// SPDX-License-Identifier: MIT
#pragma once
#include "H264Stream.h"

namespace kepler::video {

struct ParsedBaselinePicture {
    H264Picture picture{};
    uint32_t frame_num = 0, poc_lsb = 0, slice_type = 0, pps_id = 0, max_references = 0;
    int32_t delta_poc_bottom = 0;
    int8_t chroma_qp_offset = 0;
    bool constrained_intra = false, is_reference = false, is_idr = false;
    bool frame_gaps_allowed = false, p_simple_reference_controls = false;
    bool idr_no_output_prior = false, idr_long_term = false;
    std::vector<uint32_t> first_macroblocks;
    std::vector<uint8_t> annex_b;
};

// Accepts one externally delimited AVCC access unit and separate SPS/PPS NALs.
// This is a bounded header extractor, not a general or validating H.264 parser.
// It never opens a device or submits data. Output is unchanged on rejection.
bool parse_baseline_picture(const uint8_t* sps, size_t sps_size,
                            const uint8_t* pps, size_t pps_size,
                            const uint8_t* sample, size_t sample_size,
                            ParsedBaselinePicture& out) noexcept;
}
