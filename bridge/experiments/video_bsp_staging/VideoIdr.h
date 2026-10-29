// SPDX-License-Identifier: MIT
#pragma once
#include "H264Baseline.h"
#include "VideoPicture.h"

namespace kepler::video {
// Restricted CPU model for a progressive baseline IDR with zero frame/POC,
// short-term marking and no prior references. Logical identities do not prove
// ownership or GPU completion; no prepared bytes are safe to submit.
bool prepare_baseline_idr(const ParsedBaselinePicture& parsed, uint8_t target_slot,
                          uint64_t target_identity, PictureProposal& out) noexcept;
}
