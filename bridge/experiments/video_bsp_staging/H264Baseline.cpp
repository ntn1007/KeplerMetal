// SPDX-License-Identifier: MIT
#include "H264Baseline.h"
#include <limits>
#include <new>

namespace kepler::video {
namespace {
struct Bits {
    const std::vector<uint8_t>& data;
    size_t pos = 0;
    bool ok = true;
    uint32_t take(unsigned n) {
        if (n > 32 || pos > data.size() * 8 || n > data.size() * 8 - pos) { ok = false; return 0; }
        uint32_t v = 0;
        for (unsigned i = 0; i < n; ++i, ++pos) v = (v << 1) | ((data[pos / 8] >> (7 - pos % 8)) & 1u);
        return v;
    }
    uint32_t ue() {
        unsigned zeros = 0;
        while (ok && take(1) == 0) { if (++zeros > 30) { ok = false; return 0; } }
        if (!ok) return 0;
        return ((1u << zeros) - 1u) + take(zeros);
    }
    int32_t se() {
        const uint32_t v = ue();
        return (v & 1u) ? static_cast<int32_t>((v + 1u) / 2u) : -static_cast<int32_t>(v / 2u);
    }
    bool trailing_only() {
        if (!ok || take(1) != 1) return false;
        while (ok && pos < data.size() * 8) if (take(1)) return false;
        return ok;
    }
};

bool rbsp(const uint8_t* nal, size_t size, uint8_t type, std::vector<uint8_t>& out) {
    if (!nal || size < 2 || size > 0x00ffffef || (nal[0] & 0x80) || (nal[0] & 31) != type) return false;
    out.clear(); out.reserve(size - 1);
    unsigned zeros = 0;
    for (size_t i = 1; i < size; ++i) {
        const uint8_t b = nal[i];
        if (zeros >= 2 && b == 3) {
            if (i + 1 == size || nal[i + 1] > 3) return false;
            zeros = 0; continue;
        }
        out.push_back(b);
        zeros = b == 0 ? zeros + 1 : 0;
    }
    return !out.empty();
}

struct Headers {
    H264Picture picture{};
    uint32_t sps_id = 0, pps_id = 0, frame_bits = 0, poc_bits = 0;
    uint32_t l0_default = 0, l1_default = 0;
};

bool sps_header(const uint8_t* nal, size_t n, Headers& h) {
    std::vector<uint8_t> data;
    if (!rbsp(nal, n, 7, data)) return false;
    Bits b{data};
    const uint32_t profile = b.take(8), constraints = b.take(8);
    (void)b.take(8); // level
    h.sps_id = b.ue();
    const uint32_t frame_log = b.ue(), poc_type = b.ue();
    if (!b.ok || profile != 66 || (constraints & 3) || h.sps_id > 31 || frame_log > 12 || poc_type != 0) return false;
    const uint32_t poc_log = b.ue(), max_refs = b.ue();
    (void)b.take(1); // gaps_in_frame_num_value_allowed_flag
    const uint32_t width_minus_one = b.ue(), height_minus_one = b.ue();
    const uint32_t progressive = b.take(1), direct = b.take(1), cropped = b.take(1);
    const uint32_t vui_present = b.take(1); // VUI itself is deliberately not parsed
    if (!b.ok || poc_log > 12 || max_refs > 16 || !progressive || cropped ||
        width_minus_one > 4094 || height_minus_one > 4094 || (vui_present && b.pos >= data.size() * 8)) return false;
    h.frame_bits = frame_log + 4; h.poc_bits = poc_log + 4;
    h.picture.width = (width_minus_one + 1) * 16;
    h.picture.height = (height_minus_one + 1) * 16;
    h.picture.log2_max_frame_num_minus4 = frame_log;
    h.picture.pic_order_cnt_type = 0; h.picture.log2_max_pic_order_cnt_lsb_minus4 = poc_log;
    h.picture.frame_mbs_only_flag = 1; h.picture.direct_8x8_inference_flag = direct;
    return true;
}

bool pps_header(const uint8_t* nal, size_t n, Headers& h) {
    std::vector<uint8_t> data;
    if (!rbsp(nal, n, 8, data)) return false;
    Bits b{data};
    h.pps_id = b.ue(); const uint32_t sps_id = b.ue();
    const uint32_t entropy = b.take(1), bottom_poc = b.take(1), slice_groups = b.ue();
    h.l0_default = b.ue(); h.l1_default = b.ue();
    const uint32_t weighted = b.take(1), bipred = b.take(2);
    const int32_t qp = b.se(); (void)b.se(); (void)b.se();
    const uint32_t deblock = b.take(1); (void)b.take(1); const uint32_t redundant = b.take(1);
    if (!b.ok || h.pps_id > 255 || sps_id != h.sps_id || slice_groups != 0 ||
        h.l0_default > 31 || h.l1_default != 0 || bipred > 2 || qp < -26 || qp > 25 ||
        redundant || !b.trailing_only()) return false;
    h.picture.entropy_coding_mode_flag = entropy;
    h.picture.bottom_field_pic_order_in_frame_present_flag = bottom_poc;
    h.picture.weighted_pred_flag = weighted; h.picture.weighted_bipred_idc = bipred;
    h.picture.pic_init_qp_minus26 = static_cast<int8_t>(qp);
    h.picture.deblocking_filter_control_present_flag = deblock;
    return true;
}

struct Slice { uint32_t first, type, pps, frame, poc, idr, l0; int32_t delta; bool reference, is_idr; };
bool slice_header(const uint8_t* nal, size_t n, const Headers& h, Slice& s) {
    const uint8_t type = nal[0] & 31;
    std::vector<uint8_t> data;
    if ((type != 1 && type != 5) || !rbsp(nal, n, type, data)) return false;
    s.reference = (nal[0] & 0x60) != 0; s.is_idr = type == 5;
    if (s.is_idr && !s.reference) return false;
    Bits b{data}; s.first = b.ue(); s.type = b.ue(); s.pps = b.ue();
    if (!b.ok || (s.type != 0 && s.type != 2) || (s.is_idr && s.type != 2) || s.pps != h.pps_id) return false;
    s.frame = b.take(h.frame_bits); s.idr = s.is_idr ? b.ue() : 0;
    s.poc = b.take(h.poc_bits);
    s.delta = h.picture.bottom_field_pic_order_in_frame_present_flag ? b.se() : 0;
    s.l0 = 0;
    if (s.type == 0) {
        const uint32_t override_refs = b.take(1);
        s.l0 = override_refs ? b.ue() : h.l0_default;
    }
    return b.ok && s.l0 <= 31;
}
}

bool parse_baseline_picture(const uint8_t* sps, size_t sps_size,
                            const uint8_t* pps, size_t pps_size,
                            const uint8_t* sample, size_t sample_size,
                            ParsedBaselinePicture& out) noexcept {
    if (!sample || !sample_size || sample_size > 0x00ffffef) return false;
    try {
        Headers h;
        if (!sps_header(sps, sps_size, h) || !pps_header(pps, pps_size, h)) return false;
        ParsedBaselinePicture result;
        Slice first{}; bool seen = false;
        size_t pos = 0;
        while (pos < sample_size) {
            if (sample_size - pos < 4) return false;
            const uint32_t n = (uint32_t(sample[pos]) << 24) | (uint32_t(sample[pos+1]) << 16) |
                               (uint32_t(sample[pos+2]) << 8) | sample[pos+3];
            pos += 4;
            if (!n || n > sample_size - pos || (sample[pos] & 0x80)) return false;
            const uint8_t type = sample[pos] & 31;
            if (type == 1 || type == 5) {
                Slice current{};
                if (!slice_header(sample + pos, n, h, current) ||
                    current.first >= (h.picture.width / 16) * (h.picture.height / 16)) return false;
                if (!seen) { if (current.first != 0) return false; first = current; seen = true; }
                else if (current.first <= result.first_macroblocks.back() || current.type != first.type ||
                         current.pps != first.pps || current.frame != first.frame || current.poc != first.poc ||
                         current.idr != first.idr || current.delta != first.delta || current.l0 != first.l0 ||
                         current.reference != first.reference || current.is_idr != first.is_idr) return false;
                result.first_macroblocks.push_back(current.first);
                if (result.first_macroblocks.size() > 4095) return false;
            } else if (type != 6) return false; // SEI is preserved but not parsed
            result.annex_b.insert(result.annex_b.end(), {0, 0, 0, 1});
            result.annex_b.insert(result.annex_b.end(), sample + pos, sample + pos + n);
            pos += n;
        }
        if (!seen) return false;
        h.picture.slice_count = static_cast<uint32_t>(result.first_macroblocks.size());
        h.picture.num_ref_idx_l0_active_minus1 = first.l0;
        // L1 is unused for the supported I/P subset; it is zero by convention.
        h.picture.num_ref_idx_l1_active_minus1 = 0;
        result.picture = h.picture; result.frame_num = first.frame; result.poc_lsb = first.poc;
        result.slice_type = first.type; result.pps_id = first.pps;
        out = std::move(result);
        return true;
    } catch (const std::bad_alloc&) { return false; }
}
}
