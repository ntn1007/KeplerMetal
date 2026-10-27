// SPDX-License-Identifier: MIT
// Construction-only ABI control: these words are not Metal pipeline identities.
#include <metal_stdlib>
using namespace metal;
struct Root { ulong context; ulong pipeline; };
kernel void probe_boundary(device const Root &args [[buffer(0)]],
                           device ulong *out [[buffer(1)]],
                           uint gid [[thread_position_in_grid]]) {
    if (gid == 0) { out[0] = args.context; out[1] = args.pipeline; }
}
