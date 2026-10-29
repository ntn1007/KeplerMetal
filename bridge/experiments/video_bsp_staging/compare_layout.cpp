// SPDX-License-Identifier: MIT
#include "VideoLayout.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <limits>

extern "C" void mesa_reference_layout(uint32_t, uint32_t, uint32_t, uint32_t, uint64_t*);
using namespace kepler::video;

static uint32_t next(uint32_t& x) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; return x; }
int main() {
    uint32_t random = 0x9e3779b9;
    for (unsigned i = 0; i < 4096; ++i) {
        uint32_t w = 1 + next(random) % 4096, h = 1 + next(random) % 2160;
        uint32_t refs = next(random) % 17, slices = 1 + next(random) % 4095;
        if (i == 0) { w = 320; h = 240; refs = 2; slices = 2; }
        if (i == 1) { w = 1; h = 1; refs = 0; slices = 4095; }
        uint64_t expected[12]{};
        mesa_reference_layout(w, h, refs, slices, expected);
        VideoLayout got;
        assert(plan_h264_layout(w, h, refs, slices, std::numeric_limits<uint64_t>::max(), got));
        const uint64_t values[] = {got.reference_stride, got.reference_bytes, got.temporary_stride,
            got.temporary_offset, got.intermediate_bytes, got.initial_bytes, got.second_luma_offset,
            got.chroma_offset, got.second_chroma_offset, got.slice_units, got.bucket_units, got.ring_units};
        for (unsigned j = 0; j < 12; ++j) assert(values[j] == expected[j]);
        VideoLayout untouched; untouched.reference_stride = 0xdeadbeef;
        assert(!plan_h264_layout(w, h, refs, slices, got.initial_bytes - 1, untouched));
        assert(untouched.reference_stride == 0xdeadbeef);
    }
    VideoLayout result; result.reference_stride = 0xabcdef;
    auto rejected = [&](uint32_t w, uint32_t h, uint32_t r, uint32_t s) {
        assert(!plan_h264_layout(w, h, r, s, std::numeric_limits<uint64_t>::max(), result));
        assert(result.reference_stride == 0xabcdef);
    };
    rejected(0, 1, 0, 1); rejected(1, 0, 0, 1); rejected(1, 1, 17, 1);
    rejected(1, 1, 1, 0); rejected(1, 1, 1, 4096); rejected(65535, 65535, 16, 1);
    rejected(65535, 1, 1, 4095); // intermediate ring would underflow
    std::puts("PASS: 4096 Mesa layouts; bounds, budget and ring underflow refused");
}
