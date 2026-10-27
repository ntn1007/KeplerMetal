# Process-local guard for a simulated short video reply

This experiment connects a reusable C++ length policy to the existing
process-local video wrapper probe. Two signed, nonoverlapping processes created
an empty native video context on the qualified GTX profile while retaining an
ordinary Metal buffer. When the native user-mode wrapper prepared its
class-0/128 KiB request with a 49-byte response capacity, a local guarded
backend **simulated** a successful 48-byte response. The length policy rejected
it and returned an error to the wrapper before its resource-construction path.
In both runs all 16 context slots remained empty, and the 4 MiB Metal buffer
matched its CPU pattern before and after the context was released.

Two same-executable controls did not create a context or run the simulated
reply. Both positive processes returned `0xe00002c2` from the wrapper, with one
short-reply rejection, one guarded struct attempt and no unexpected guarded
calls. The guard did not forward selector 3 or fabricate a usable resource.
The previous invalid-class and null-resource checks remained in place. The
[audit record](video-reply-gate-validation.json) binds the exact build and
receipts and rejects eleven offline mutations.

The simulated status and length are generated *inside the process*, not by the
kernel. This does not establish that the real driver returns short replies,
that a complete real reply is safe, or that a video buffer can be allocated.
The guard is experimental and is not automatically installed in applications,
macOS or the NVIDIA driver. No video decoding or GPU computation is shown.

## Scope and policy

[`reply_gate.h`](../bridge/experiments/video_reply_gate/reply_gate.h) classifies
backend failure, a full-length success, a length mismatch, or an invalid local
profile. It checks lengths and capacity only; it does not examine or validate
resource fields, ownership, synchronization or cleanup. The 4 KiB maximum is a
project safety bound, not a discovered driver limit. A standalone C++ test
checks complete and incomplete sizes, an existing backend failure, invalid
capacity and an overflow-sized private length. A complete simulated success is
**not** passed to the native resource constructor: that would require a real,
qualified response and ownership contract.

The host checks the device/shared/resource identity, native function hashes and
six import slots and calibrates the same bounded guard described in the
[preceding request test](VIDEO_BUFFER_REQUEST_GUARD.md). It allows the already
qualified empty-context open, association and release, and intercepts the
request on the probe thread. The cooperative reservation does not exclude
WindowServer or unrelated processes; guard coverage is not a complete system
trace. Ordinary Metal may perform its own driver operations. No driver, system
framework, OCLP setting or firmware was modified.

## Reproduction

Use the exact pinned profile and current verified registry ID, the shared lab
reservation, and fresh paths. `coexist` performs the simulated short response;
`observe` is the same-build control. The optional historical input checks the
two earlier synthetic NVIDIA-provider observations.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified nvAccelerator registry ID>'
EXP=bridge/experiments/video_reply_gate
(
  set -e
  xcrun clang++ -std=c++17 tests/test_video_reply_gate.cpp -o "$LAB/results/reply-policy-test-new"
  "$LAB/results/reply-policy-test-new"
  python3 "$EXP/experiment.py" build --out "$LAB/results/reply-gate-build-new"
  for item in observe:1 coexist:1 observe:2 coexist:2; do
    mode=${item%:*}; n=${item#*:}
    python3 "$EXP/experiment.py" run --build "$LAB/results/reply-gate-build-new" \
      --out "$LAB/results/reply-gate-$mode-$n" --lab "$LAB" --registry-id "$RID" --mode "$mode"
  done
  python3 "$EXP/audit.py" --build "$LAB/results/reply-gate-build-new" \
    --runs "$LAB/results/reply-gate-observe-1" "$LAB/results/reply-gate-coexist-1" \
      "$LAB/results/reply-gate-observe-2" "$LAB/results/reply-gate-coexist-2" \
    --history "$LAB/results/video-sierra-request-refused-positive-20261027-01/result.json" \
      "$LAB/results/video-sierra-request-refused-positive-20261027-02/result.json" \
    --out "$LAB/results/reply-gate-audit-new.json"
)
```

The signed hosts and private vendor captures remain in the lab. The next
milestone requires qualification of the actual kernel output and resource
lifetime; the gate alone is not authorization to forward an unqualified request.
