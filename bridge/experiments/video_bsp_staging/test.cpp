// SPDX-License-Identifier: MIT
#include "H264Stream.h"
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <vector>

using namespace kepler::video;

int main() {
    const uint8_t a[] = {0, 0, 1, 0x67, 9};
    const uint8_t b[] = {0, 1, 0x65};
    const ByteChunk chunks[] = {{a, sizeof(a)}, {nullptr, 0}, {b, sizeof(b)}};
    std::vector<uint8_t> out;
    assert(stage_h264_stream(chunks, 3, out) == StagingStatus::ok);
    assert(out.size() == 0x700 + sizeof(a) + sizeof(b) + 16);
    assert(out[0x100] == 24 && out[0x101] == 0 && out[0x110] == 1);
    assert(std::equal(a, a + sizeof(a), out.begin() + 0x700));
    assert(std::equal(b, b + sizeof(b), out.begin() + 0x700 + sizeof(a)));
    const uint8_t tail[] = {0, 0, 1, 0x0b, 0, 0, 0, 0, 0, 0, 1, 0x0b, 0, 0, 0, 0};
    assert(std::equal(tail, tail + sizeof(tail), out.end() - sizeof(tail)));
    const auto saved = out;
    ByteChunk bad{nullptr, 1};
    assert(stage_h264_stream(&bad, 1, out) == StagingStatus::invalid_input && out == saved);
    assert(stage_h264_stream(nullptr, 1, out) == StagingStatus::invalid_input && out == saved);
    ByteChunk huge{a, 0x00ffffff};
    assert(stage_h264_stream(&huge, 1, out) == StagingStatus::too_large && out == saved);
    assert(stage_h264_stream(nullptr, 0, out) == StagingStatus::ok && out.size() == 0x710);
    assert(out[0x100] == 16 && out[0x110] == 1);
    std::vector<uint8_t> boundary(0x00ffffff - 16, 0xa5);
    ByteChunk largest{boundary.data(), boundary.size()};
    assert(stage_h264_stream(&largest, 1, out) == StagingStatus::ok);
    assert(out[0x100] == 0xff && out[0x101] == 0xff && out[0x102] == 0xff && out[0x103] == 0);
    const ByteChunk overflow[] = {largest, {a, 1}};
    const size_t old_size = out.size();
    assert(stage_h264_stream(overflow, 2, out) == StagingStatus::too_large);
    assert(out.size() == old_size && out[0x100] == 0xff && out[0x700] == 0xa5);
}
