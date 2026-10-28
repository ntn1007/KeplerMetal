// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>
#include <limits>

// Necessary conditions for one explicitly serialized, observed alias release.
// This is not a proof of ownership or a substitute for lifecycle coordination.
namespace kepler_video {
struct AliasEvidence {
 bool extra_acquired, same_name, metal_self_equal, extra_self_equal, object_equal;
 int before_status, opened_status;
 uint32_t before_refs, opened_refs;
};
inline bool allowsReferenceRelease(const AliasEvidence &e) noexcept {
 return e.extra_acquired && e.same_name && e.metal_self_equal && e.extra_self_equal && e.object_equal &&
        e.before_status==0 && e.opened_status==0 && e.before_refs>0 &&
        e.before_refs<std::numeric_limits<uint32_t>::max() && e.opened_refs==e.before_refs+1;
}
}
