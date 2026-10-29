// SPDX-License-Identifier: MIT
#pragma once
#include "H264Stream.h"
#include <array>
#include <cstdint>

namespace kepler::video {
struct ReferenceState {
    uint64_t identity = 0; // caller-owned logical identity, never a GPU address
    bool field_picture = false, decoded_top = false, decoded_bottom = false, decoded_first = false;
};
struct PictureReference {
    uint64_t identity = 0;
    uint8_t slot = 0;
    bool top = false, bottom = false, long_term = false;
    int32_t top_order = 0, bottom_order = 0;
    uint32_t frame_index = 0;
};
struct VideoPicture {
    H264Picture picture{};
    uint8_t max_references = 0, reference_count = 0, target_slot = 0;
    uint64_t target_identity = 0;
    bool constrained_intra = false, is_reference = false;
    int8_t chroma_qp_offset = 0, second_chroma_qp_offset = 0;
    uint16_t frame_number = 0;
    int32_t top_order = 0, bottom_order = 0;
    std::array<uint8_t, 96> scaling4{};
    std::array<uint8_t, 128> scaling8{};
    std::array<ReferenceState, 17> slots{};
    std::array<PictureReference, 16> refs{};
};
struct PictureProposal {
    std::array<uint8_t, 756> bytes{};
    uint32_t caps = 0;
    uint8_t target_slot = 0;
    ReferenceState target_after{};
};

// CPU model only. The proposed state is not evidence of GPU completion and
// must not be committed by a caller without a separately qualified protocol.
// An invalid input leaves out unchanged. No hardware submission is allowed.
bool prepare_video_picture(const VideoPicture& picture, PictureProposal& out) noexcept;
}
