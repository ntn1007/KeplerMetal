# A real video context attached to Metal's shared object

A process-local Metal observer now uses the actual `IOAccelShared` object returned during the GTX 880M's normal Metal initialization to create an **empty** video-context wrapper. This is an explicit experimental call to the current private `IOAccelVideoContextCreate`, not a call to the historical NVIDIA video provider. The shared object remains owned by its original caller and is returned unchanged after the short experiment; the new context is released in the same call.

Two signed, separate test processes each observed:

- one type-3 `IOServiceOpen` on the already identified GTX service, status 0;
- one `IOConnectAddClient` using that context connection and the Metal shared connection, status 0;
- a non-null context whose CoreFoundation type, stored shared pointer and connection match the expected live objects;
- 16 wrapper slots, all observed empty, followed by one `IOConnectRelease`, status 0.

Two same-executable control processes performed no context creation. The Metal client also checks the CPU bytes of its ordinary shared buffer. Each experiment is serialized under the cooperative lab reservation; all four processes and receipts are terminal. The [offline audit](video-context-object-validation.json) checks source and executable identities, object/configuration observations, statuses, empty slots and seven mutated-result or receipt controls.

Before enabling the experiment, it verifies the exact loaded code hashes of the constructor, release, getters and context finalizer, plus the shared/device profile. On the probe thread it checks that six IOAccelerator import slots resolve to the observer's guards, and calibrates their refusal behavior. Only type-3 open on the selected service, association of the observed context/shared connections and release of that context are forwarded. Method, scalar and struct selector calls observed through those guarded imports on that thread are refused; none occurred in these two experiments. This is not exhaustive monitoring of every driver or framework path, nor does the cooperative reservation exclude WindowServer.

A successful empty wrapper and accepted association do **not** establish a valid video buffer, complete ownership/teardown, a live selector ABI, hardware-video execution or a speed gain. The 16 observed slots are wrapper capacity, not evidence of 16 valid kernel resource classes. Ordinary Metal initialization may perform internal driver activity outside the probe. No system driver or OCLP component is modified.

This links the [real Metal device/shared observations](METAL_SHARED_OBJECT.md) with the earlier [raw connection association](VIDEO_CONTEXT_ASSOCIATION.md), using the native wrapper rather than manually constructing a synthetic pointer. A next step must qualify a genuine resource and its complete lifetime before any video command or unqualified selector is sent.

## Reproduction

Use the pinned host profile, a fresh build and output paths, common lab root `LAB`, and its current qualified GTX `nvAccelerator` registry ID `RID`. `context` mode performs the explicit private context creation and immediate release; `observe` is the control. Do not use a changed profile without separate qualification.

```sh
(
set -e
python3 bridge/experiments/video_context_object/experiment.py build --out "$LAB/results/video-context-object-build-new"
for item in observe:1 context:1 observe:2 context:2; do
  mode=${item%:*}; number=${item#*:}
  python3 bridge/experiments/video_context_object/experiment.py run \
    --build "$LAB/results/video-context-object-build-new" --out "$LAB/results/video-context-object-$mode-$number" \
    --lab "$LAB" --registry-id "$RID" --mode "$mode"
done
python3 bridge/experiments/video_context_object/audit.py --build "$LAB/results/video-context-object-build-new" \
  --runs "$LAB/results/video-context-object-observe-1" "$LAB/results/video-context-object-context-1" \
    "$LAB/results/video-context-object-observe-2" "$LAB/results/video-context-object-context-2" \
  --out "$LAB/results/video-context-object-audit-new.json"
)
```

The signed host artifacts and captured proprietary bytes stay in the local lab; the repository contains only the experiment's original source and scalar evidence.
