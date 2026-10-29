// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>

namespace kepler::video {
struct VideoLayout {
    uint64_t reference_stride = 0, reference_bytes = 0;
    uint64_t temporary_stride = 0, temporary_offset = 0;
    uint64_t intermediate_bytes = 0, initial_bytes = 0;
    uint64_t second_luma_offset = 0, chroma_offset = 0, second_chroma_offset = 0;
    uint32_t slice_units = 0, bucket_units = 0, ring_units = 0;
};

// CPU-only initial allocation planning. No addresses, GPU allocations or
// driver calls. `budget` applies to this incomplete estimate only.
bool plan_h264_layout(uint32_t width, uint32_t height, uint32_t max_references,
                      uint32_t slice_count, uint64_t budget, VideoLayout& out) noexcept;
}
