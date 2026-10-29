// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>
#include <cstring>

// This is a test-only counterfactual, not an NVIDIA capability predicate.
inline bool KPCodecProbeAllowed(const char *mode, bool pinned, uint64_t offset,
                                bool keyMatches, bool classMatches, bool idMatches,
                                bool originalNull, uint32_t options) {
    return mode && !std::strcmp(mode,"synthetic") && pinned && offset==150812 && keyMatches &&
           classMatches && idMatches && originalNull && options==0;
}
