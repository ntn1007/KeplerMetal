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

// CPU-only stream staging. The returned bytes contain no qualified picture
// descriptor, GPU addresses, channel commands, or submission capability.
enum class StagingStatus { ok, invalid_input, too_large, allocation_failed };
StagingStatus stage_h264_stream(const ByteChunk* chunks, size_t count,
                                std::vector<uint8_t>& out) noexcept;

} // namespace kepler::video
