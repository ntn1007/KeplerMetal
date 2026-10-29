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
} // namespace kepler::video
