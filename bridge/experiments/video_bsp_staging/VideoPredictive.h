// SPDX-License-Identifier: MIT
#pragma once
#include "H264Baseline.h"
#include "VideoPicture.h"

namespace kepler::video {
// CPU-only, deliberately narrow progressive baseline P-picture proposal.
// The caller supplies a chronological, already-decoded logical DPB with up to
// two short-term references and a distinct fresh target. No real surface,
// GPU completion or hardware video compatibility is established here.
// The caller must not submit the resulting bytes to a GPU. Output is unchanged
// on rejection; input states are never updated.
bool prepare_baseline_p(const ParsedBaselinePicture& parsed,
                        const std::array<ReferenceState, 17>& slots,
                        const std::array<PictureReference, 2>& refs,
                        uint8_t reference_count, uint8_t target_slot,
                        uint64_t target_identity, PictureProposal& out) noexcept;
}
