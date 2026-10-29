// SPDX-License-Identifier: MIT
#include "H264Baseline.h"
#include "VideoLayout.h"
#include <cassert>
#include <cstdint>
#include <vector>

using namespace kepler::video;
struct Writer {
    std::vector<uint8_t> bytes;
    unsigned bit_count = 0;
    void bits(uint32_t v, unsigned n) {
        for (unsigned i = n; i; --i) {
            if (!(bit_count % 8)) bytes.push_back(0);
            bytes.back() |= ((v >> (i - 1)) & 1u) << (7 - bit_count % 8);
            ++bit_count;
        }
    }
    void ue(uint32_t value) {
        const uint32_t code = value + 1; unsigned n = 0;
        for (uint32_t x = code; x; x >>= 1) ++n;
        bits(0, n - 1); bits(code, n);
    }
    void se(int value) { ue(value <= 0 ? static_cast<uint32_t>(-2 * value) : static_cast<uint32_t>(2 * value - 1)); }
    void finish() { bits(1, 1); while (bit_count % 8) bits(0, 1); }
};

static std::vector<uint8_t> sps() {
    Writer w; w.bits(66, 8); w.bits(0, 8); w.bits(13, 8);
    w.ue(0); w.ue(1); w.ue(0); w.ue(3); w.ue(2); w.bits(0, 1);
    w.ue(19); w.ue(14); w.bits(1, 1); w.bits(1, 1); w.bits(0, 1); w.bits(0, 1); w.finish();
    w.bytes.insert(w.bytes.begin(), 0x67); return w.bytes;
}
static std::vector<uint8_t> pps(int chroma = 0, bool constrained = false) {
    Writer w; w.ue(0); w.ue(0); w.bits(0, 1); w.bits(1, 1); w.ue(0); w.ue(0); w.ue(0);
    w.bits(0, 1); w.bits(0, 2); w.se(2); w.se(0); w.se(chroma); w.bits(0, 1); w.bits(constrained, 1); w.bits(0, 1); w.finish();
    w.bytes.insert(w.bytes.begin(), 0x68); return w.bytes;
}
static std::vector<uint8_t> idr_slice(uint32_t first, bool no_output, bool long_term) {
    Writer w; w.ue(first); w.ue(2); w.ue(0); w.bits(0,5); w.ue(0); w.bits(0,7); w.se(0);
    w.bits(no_output,1); w.bits(long_term,1); w.finish();
    w.bytes.insert(w.bytes.begin(),0x65); return w.bytes;
}
static std::vector<uint8_t> slice(uint32_t first, uint32_t frame, uint32_t type = 0, int ref_override = -1, int controls = -1) {
    Writer w; w.ue(first); w.ue(type); w.ue(0); w.bits(frame, 5); w.bits(2, 7); w.se(0);
    w.bits(ref_override >= 0, 1); if (ref_override >= 0) w.ue(static_cast<uint32_t>(ref_override));
    if (controls >= 0) { w.bits(controls == 1, 1); if (controls != 1) w.bits(controls == 2, 1); }
    w.finish();
    w.bytes.insert(w.bytes.begin(), 0x41); return w.bytes;
}
static void append(std::vector<uint8_t>& out, const std::vector<uint8_t>& n) {
    uint32_t len = static_cast<uint32_t>(n.size());
    out.push_back(len >> 24); out.push_back(len >> 16); out.push_back(len >> 8); out.push_back(len);
    out.insert(out.end(), n.begin(), n.end());
}

int main() {
    const auto s = sps(), p = pps();
    std::vector<uint8_t> sample; append(sample, slice(0, 1)); append(sample, slice(150, 1));
    ParsedBaselinePicture out;
    assert(parse_baseline_picture(s.data(), s.size(), p.data(), p.size(), sample.data(), sample.size(), out));
    assert(out.picture.width == 320 && out.picture.height == 240 && out.picture.slice_count == 2 && out.max_references == 2);
    assert(out.frame_num == 1 && out.poc_lsb == 2 && out.first_macroblocks == std::vector<uint32_t>({0, 150}));
    assert(out.picture.pic_init_qp_minus26 == 2 && out.picture.num_ref_idx_l0_active_minus1 == 0);
    assert(out.is_reference && !out.is_idr && !out.chroma_qp_offset && !out.constrained_intra);
    std::vector<uint8_t> simple; append(simple,slice(0,1,0,-1,0)); append(simple,slice(150,1,0,-1,0));
    ParsedBaselinePicture controls;
    assert(parse_baseline_picture(s.data(),s.size(),p.data(),p.size(),simple.data(),simple.size(),controls));
    assert(controls.p_simple_reference_controls && !controls.frame_gaps_allowed);
    std::vector<uint8_t> modified; append(modified,slice(0,1,0,-1,0)); append(modified,slice(150,1,0,-1,1));
    assert(parse_baseline_picture(s.data(),s.size(),p.data(),p.size(),modified.data(),modified.size(),controls));
    assert(!controls.p_simple_reference_controls);
    std::vector<uint8_t> adaptive; append(adaptive,slice(0,1,0,-1,2));
    assert(parse_baseline_picture(s.data(),s.size(),p.data(),p.size(),adaptive.data(),adaptive.size(),controls));
    assert(!controls.p_simple_reference_controls);
    const auto rich_pps=pps(-4,true); std::vector<uint8_t> idr;
    append(idr,idr_slice(0,false,false)); append(idr,idr_slice(150,false,false));
    ParsedBaselinePicture parsed_idr;
    assert(parse_baseline_picture(s.data(),s.size(),rich_pps.data(),rich_pps.size(),idr.data(),idr.size(),parsed_idr));
    assert(parsed_idr.is_idr && parsed_idr.is_reference && parsed_idr.chroma_qp_offset==-4 &&
           parsed_idr.constrained_intra && !parsed_idr.delta_poc_bottom && !parsed_idr.idr_long_term);
    std::vector<uint8_t> marked; append(marked,idr_slice(0,true,true));
    ParsedBaselinePicture marked_idr;
    assert(parse_baseline_picture(s.data(),s.size(),p.data(),p.size(),marked.data(),marked.size(),marked_idr));
    assert(marked_idr.is_idr && marked_idr.idr_no_output_prior && marked_idr.idr_long_term);
    VideoLayout layout;
    assert(plan_h264_layout(out.picture.width, out.picture.height, out.max_references,
                            out.picture.slice_count, 11161600, layout));
    assert(layout.reference_stride == 122880 && layout.reference_bytes == 675840 && layout.initial_bytes == 11161600);
    VideoLayout rejected_layout; rejected_layout.reference_stride = 0x1234;
    assert(!plan_h264_layout(320, 240, 2, 2, 11161599, rejected_layout));
    assert(rejected_layout.reference_stride == 0x1234);
    std::vector<uint8_t> override_sample;
    append(override_sample, slice(0, 1, 0, 2)); append(override_sample, slice(150, 1, 0, 2));
    ParsedBaselinePicture overridden;
    assert(parse_baseline_picture(s.data(), s.size(), p.data(), p.size(), override_sample.data(), override_sample.size(), overridden));
    assert(overridden.picture.num_ref_idx_l0_active_minus1 == 2);
    const auto before = out.annex_b;
    auto reject = [&](const std::vector<uint8_t>& ss, const std::vector<uint8_t>& pp, const std::vector<uint8_t>& aa) {
        assert(!parse_baseline_picture(ss.data(), ss.size(), pp.data(), pp.size(), aa.data(), aa.size(), out));
        assert(out.annex_b == before && out.frame_num == 1);
    };
    reject(s,pps(13),sample); reject(s,pps(-13),sample);
    std::vector<uint8_t> mixed_idr; append(mixed_idr,idr_slice(0,false,false)); append(mixed_idr,idr_slice(150,false,true));
    reject(s,p,mixed_idr);
    for (size_t i = 0; i < s.size(); ++i) reject(std::vector<uint8_t>(s.begin(), s.begin() + i), p, sample);
    for (size_t i = 0; i < p.size(); ++i) reject(s, std::vector<uint8_t>(p.begin(), p.begin() + i), sample);
    for (size_t i = 0; i < sample.size(); ++i) {
        // A prefix ending exactly after the first complete slice is a possible
        // shorter access unit; test only cuts inside its first length/NAL.
        if (i < 4 + slice(0, 1).size()) reject(s, p, std::vector<uint8_t>(sample.begin(), sample.begin() + i));
    }
    auto invalid_sps = s; invalid_sps[1] = 100; reject(invalid_sps, p, sample);
    std::vector<uint8_t> mixed; append(mixed, slice(0, 1)); append(mixed, slice(150, 2)); reject(s, p, mixed);
    std::vector<uint8_t> mixed_refs; append(mixed_refs, slice(0, 1, 0, 2)); append(mixed_refs, slice(150, 1, 0, 1)); reject(s, p, mixed_refs);
    std::vector<uint8_t> bad_refs; append(bad_refs, slice(0, 1, 0, 32)); reject(s, p, bad_refs);
    std::vector<uint8_t> bad_first; append(bad_first, slice(150, 1)); reject(s, p, bad_first);
    std::vector<uint8_t> b_slice; append(b_slice, slice(0, 1, 1)); reject(s, p, b_slice);
    auto idr_p = sample; idr_p[4] = 0x65; reject(s, p, idr_p);
    auto bad_length = sample; bad_length[0] = 1; reject(s, p, bad_length);
    auto bad_type = sample; bad_type[4] = 0x69; reject(s, p, bad_type);
    assert(!parse_baseline_picture(nullptr, 0, p.data(), p.size(), sample.data(), sample.size(), out));
    assert(out.annex_b == before);
}
