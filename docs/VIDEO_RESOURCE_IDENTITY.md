# Metal buffer to shared IOAccelerator resource: bounded observation

On the pinned iMac profile, two separate signed, unprivileged processes each
created an ordinary 4 MiB shared `MTLBuffer` through the public Metal API and
checked every byte with the CPU. The observer recorded the device and
`IOAccelShared` objects produced by the ordinary Metal initialization path,
using the previously qualified [device/shared checks](METAL_VIDEO_CONTEXT.md).
The buffer remained alive while its resource field was inspected. The observed
resource pointer was nonzero in both processes, and a bounded read at offset
`0x18` of the pointed-to memory matched the actual shared-wrapper pointer in
both. The null-resource negative check returned false twice.

This strengthens the earlier temporal [allocation observation](VIDEO_METAL_RESOURCE_OBSERVER.md):
for these two Metal buffers it ties a field used by Metal's `resourceRef`
accessor to the same shared wrapper that Metal constructed for the selected
GTX. It does **not** show that the resource is a video data buffer, that it can
be bound to the empty video context, that the accessor was called, that the
resource finalizer ran, or that any GPU command or video decoder executed. No
new private resource function or selector is called by this experiment. The
previously established static `CFRetain` relationship is separate evidence;
a pointer match is not an independent lifetime or type proof.

## How the field is located

The program checks Objective-C runtime metadata for `_res` and the method type
of `resourceRef`. It then verifies the loaded `MetalOld.dylib` image, exact
getter location and SHA-256 of 18 bytes of its implementation. Inspection of
the pinned getter shows a read of an offset variable followed by a read at
`offset + 0x70`; the program verifies that the offset variable and the `_res`
metadata both equal 24, giving the slot at byte 136. It reads only that slot
and the candidate resource's shared-wrapper field using bounded
`mach_vm_read_overwrite`. It does not call the getter, retain the candidate,
or write to either object. No raw pointer or proprietary instruction bytes are
included in the published result.

The seven audit mutations reject changed matches, missing objects, a failed
null control, a claimed getter call, a changed getter hash or slot, and a
nonterminal reservation. These are offline audit controls, not seven new GPU
experiments. The cooperative reservation does not exclude WindowServer or
other unrelated processes. Normal Metal allocation and cleanup still use the
existing driver; this test does not characterize every operation they perform.

A separate exploratory CPU-only attempt to derive the nested layout via
`NSGetSizeAndAlignment` raised `NSInvalidArgumentException` on the bitfield
encoding. It did not use Metal or the GPU. That failure is retained locally;
the final observation relies on the pinned getter instead of assuming the
bitfield layout. An earlier experimental build also failed due to a missing
header, before being corrected. These failures are not counted as successful
hosts.

## Reproduction

Use the exact qualified profile and a fresh output path for each step. The
existing runner checks the pinned system profile, freezes inputs, signs copies,
serializes participating GPU tests and checks terminal state. The resource
identity audit imports the earlier device/context audit for the shared-object
and execution-manifest checks. Read both tools before use.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified nvAccelerator registry ID>'
EXP=bridge/experiments/video_resource_identity
python3 "$EXP/experiment.py" build --out "$LAB/results/resource-identity-build-new"
for n in 1 2; do
  python3 "$EXP/experiment.py" run --build "$LAB/results/resource-identity-build-new" \
    --out "$LAB/results/resource-identity-run-$n" --lab "$LAB" --registry-id "$RID" --mode observe || break
done
python3 "$EXP/audit.py" --build "$LAB/results/resource-identity-build-new" \
  --runs "$LAB/results/resource-identity-run-1" "$LAB/results/resource-identity-run-2" \
  --out "$LAB/results/resource-identity-audit-new.json"
```

The [sanitized validation record](video-resource-identity-validation.json)
contains result and manifest hashes. The private captures, binaries and host
logs remain in the lab. No system file, driver, OCLP setting or firmware was
modified. The next question is whether a separately qualified, suitable
video-data-buffer producer can be identified; a generic Metal allocation must
not be substituted for one merely because the shared wrapper matches.
