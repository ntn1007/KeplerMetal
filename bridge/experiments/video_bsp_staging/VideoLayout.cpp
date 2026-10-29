// SPDX-License-Identifier: MIT
#include "VideoLayout.h"
#include <limits>

namespace kepler::video {
bool plan_h264_layout(uint32_t width, uint32_t height, uint32_t max_references,
                      uint32_t slice_count, uint64_t budget, VideoLayout& out) noexcept {
    if (!width || !height || width > 65535 || height > 65535 || max_references > 16 ||
        !slice_count || slice_count > 4095) return false;
    const uint64_t w = (uint64_t(width) + 15) / 16;
    const uint64_t half_w = (uint64_t(width) + 31) / 32;
    const uint64_t half_h = (uint64_t(height) + 31) / 32;
    const uint64_t aligned_h = ((uint64_t(height) + 63) / 64) * 64;
    const uint64_t raw_intermediate = uint64_t(width) * height * 2;
    constexpr uint64_t kAlignment = 4u * 1024u * 1024u;
    const uint64_t intermediate = ((raw_intermediate + kAlignment - 1) / kAlignment) * kAlignment;
    VideoLayout result;
    result.reference_stride = w * 16 * (half_h * 32 + aligned_h / 2);
    result.temporary_stride = 16 * half_w * aligned_h * 3 / 2;
    result.temporary_offset = result.reference_stride * (max_references + 2);
    result.reference_bytes = result.temporary_offset + result.temporary_stride * (max_references + 1);
    result.intermediate_bytes = intermediate;
    result.second_luma_offset = half_h * w * 256;
    result.chroma_offset = 2 * result.second_luma_offset;
    result.second_chroma_offset = result.chroma_offset + w * (aligned_h / 64) * 256;
    const uint64_t slice_units = uint64_t(slice_count) * 2;
    const uint64_t bucket_units = w * 3;
    if (intermediate / 256 < slice_units + bucket_units) return false;
    const uint64_t ring_units = intermediate / 256 - slice_units - bucket_units;
    // Keep source calculations in the range represented by Mesa's 32-bit fields.
    const uint64_t max32 = std::numeric_limits<uint32_t>::max();
    if (raw_intermediate > max32 || intermediate > max32 || result.reference_stride > max32 ||
        result.temporary_stride > max32 || result.reference_bytes > max32 || ring_units > max32 ||
        result.second_chroma_offset > result.reference_stride ||
        2 * (result.second_chroma_offset - result.chroma_offset) + result.chroma_offset > result.reference_stride)
        return false;
    result.slice_units = static_cast<uint32_t>(slice_units);
    result.bucket_units = static_cast<uint32_t>(bucket_units);
    result.ring_units = static_cast<uint32_t>(ring_units);
    // Mesa's non-debug initial plan uses two 1 MiB BSP buffers and two
    // intermediate buffers. It may grow; this excludes other allocations.
    result.initial_bytes = result.reference_bytes + 2 * intermediate + 2 * 1024 * 1024;
    if (result.initial_bytes > budget) return false;
    out = result;
    return true;
}
}
