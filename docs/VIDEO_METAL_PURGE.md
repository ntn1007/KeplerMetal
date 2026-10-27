# Metal buffer purgeability on the pinned NVIDIA stack

This is a bounded qualification of an **existing public Metal API**, not a new driver feature. In three fresh unprivileged processes on the pinned GTX 880M profile, a 4 MiB shared buffer was written and checked by the CPU, marked `Empty`, returned to `NonVolatile`, and rewritten and checked in full. Three interleaved processes created and checked an equivalent buffer without changing its purgeability. A separate signed process calibrated the IOKit observer before the cohort. No GPU commands or private device selectors were submitted.

[Apple's `setPurgeableState:` documentation](https://developer.apple.com/documentation/metal/mtlresource/setpurgeablestate%28_%3A%29) specifies that its return is the **previous** state, `KeepCurrent` queries the state, and `Empty` declares the contents discardable. The bytes were deliberately not read while the resource was empty; the experiment does not expect their old values to survive. It queries `NonVolatile` after restoring and only then writes the new pattern.

Each of the three transition trials returned this sequence:

| Operation | Returned state |
| --- | --- |
| Query initial state | NonVolatile |
| Set Empty | NonVolatile, the previous state |
| Query state | Empty |
| Set NonVolatile | Empty, the previous state |
| Query state | NonVolatile |

The full 4 MiB pattern written **after** restoration was correct in all three trials, and the target object's weak reference cleared after release and pool drain. The observer captured one IOAccelResourceCreate completion in the target creation phase in each of the six large-buffer processes, but no IOKit events during the purge/query/restore/check phases and no shared-client selector-1 event within the captured window. Interposition is incomplete and phases denote call completion, so this is not evidence that the driver did not call another interface, that an internal resource was destroyed, or that physical memory was reclaimed. The static deletion contract remains unverified at runtime. No contents before versus after `Empty` were compared. The test does not establish GPU access after a purge, video decoding, or performance improvement.

The [sanitized audit](video-metal-purge-validation.json) includes the recorded state sequence, counts and hashes of retained local results and execution manifests. It checks the source/executable fingerprints, signed test host and observer, unique process IDs, target identity, ordering, calibration, creation observations, state returns and CPU oracle. Raw captures and system binaries remain local. No installed driver or framework is modified.

## Reproduction

The same pinned build, inventory and reservation instructions as the [resource observer](VIDEO_METAL_RESOURCE_OBSERVER.md) apply. Run `control` first and require `HOOK_CONTROLS_PASS`; stop on any refusal or profile change. Set `LAB` to the cooperative lab reservation root and `RID` to the fresh inventory GPU registry ID; all output names must be new. Using a build compiled from the current source:

```sh
for item in control:01 large:01 purge:01 large:02 purge:02 large:03 purge:03; do
  mode=${item%:*}
  number=${item#*:}
  python3 bridge/tools/video_metal_resource_observer.py run \
    --build "$LAB/results/resource-build-new" \
    --out "$LAB/results/purge-${mode}-${number}" \
    --reservation-root "$LAB" --mode "$mode" --registry-id "$RID" || break
done
python3 bridge/tools/audit_video_metal_purge.py \
  "$LAB/results/purge-control-01" \
  "$LAB/results/purge-large-01" "$LAB/results/purge-purge-01" \
  "$LAB/results/purge-large-02" "$LAB/results/purge-purge-02" \
  "$LAB/results/purge-large-03" "$LAB/results/purge-purge-03"
```

The run-level oracle preserves a complete diagnostic even if the returned states are not the sequence above; the cohort auditor reports failure rather than claiming a successful transition. A failed, timed-out or incomplete process must be inspected under the reservation rules before another test.
