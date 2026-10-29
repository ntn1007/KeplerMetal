# Device and shared objects during a public VideoToolbox request

On the pinned iMac profile, two observed hardware-required VideoToolbox
session-creation windows each included one natural
`IOAccelDeviceCreateWithAPIProperty` return and one natural
`IOAccelSharedCreate` return. The host selected a unique `nvAccelerator` whose
PCI ancestor reported NVIDIA `10de:1198`. While the original objects were
inside those creation calls, the observer's pinned runtime type checks passed;
the shared constructor received the selected device pointer, and a bounded
read of its pinned `0x10` field matched that pointer. Neither pointer was
exported or retained by the observer.

This is a **temporal process-local observation**: the window includes the
public VideoToolbox call and framework activity, but the caller thread and the
subsequent consumer of these objects were not established. It does not prove
that the failed decoder retained or used them, that their later lifetimes are
safe, or that a video context or hardware decoder was created. Both requests
still returned **`-12906`** and zero images.

## Controls

The same [previously qualified observer](METAL_SHARED_OBJECT.md) was enabled
for a public Metal control. Two observed controls found the same bounded
device/shared relationship; two plain controls also completed their public
4 KiB shared-buffer CPU checks. These controls are not GPU-compute tests. Two
observed and two plain software VideoToolbox processes decoded 24 frames in
total, matching **2,764,800 active NV12 reference bytes**. Their hardware
property query returned `-12900` and null, while their session specification
explicitly disabled hardware; the query is not treated as false. No matching
device/shared constructor was observed through the interposed calls in the two
software windows. Two plain hardware-required processes also returned `-12906`
and zero frames.

The 12 signed processes used the same frozen build, separate nonoverlapping
cooperative reservations and terminal receipts. The host checks the unique PCI
ancestor in each process but does not retain the raw registry IDs in its
result; the auditor also checks the display inventory at audit time. The
observer forwards the original constructor calls and returns their values; it
checks the loaded constructor/type-getter code before reading type-related
state. It calls no private configuration getter in this cohort, constructs no
wrapper and sends no video selector. It may miss uninstrumented bindings,
calls before its active window or activity in other processes, and the
reservation does not exclude WindowServer.

[Independent audit](video-vt-object-observer-validation.json) checks the
build, signatures, source and result hashes, software pixels, target and type
flags, nonoverlapping terminal process receipts and observer modes. Four
[offline mutations](video-vt-object-observer-mutations.json) alter the shared
link, device type, configuration-call count or hardware status and are
rejected even after recalculating the output hash. They are not additional GPU
runs. Three system-file hashes were checked before and after each process;
GeForce and IOAcceleratorFamily2 on-disk hashes and GPU inventory were checked
at audit time, not as loaded-kernel bytes. No system driver, framework, OCLP or
firmware was changed.

## Reproduction

Use the retained fixture/reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md),
the pinned observer source and a fresh laboratory output for each process:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/video_vt_object_observer
B="$LAB/results/vt-object-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --fixture /path/to/fixture \
  --reference /path/to/decoded.nv12 --out "$B"
for n in 1 2; do
  for mode in metal-observed hardware-observed metal-plain software-observed hardware-plain software-plain; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" \
      --out "$LAB/results/vt-object-$mode-$n-new" || break 2
  done
done
RUNS=("$LAB/results/vt-object-metal-observed-1-new" "$LAB/results/vt-object-hardware-observed-1-new"
      "$LAB/results/vt-object-metal-plain-1-new" "$LAB/results/vt-object-software-observed-1-new"
      "$LAB/results/vt-object-hardware-plain-1-new" "$LAB/results/vt-object-software-plain-1-new"
      "$LAB/results/vt-object-metal-observed-2-new" "$LAB/results/vt-object-hardware-observed-2-new"
      "$LAB/results/vt-object-metal-plain-2-new" "$LAB/results/vt-object-software-observed-2-new"
      "$LAB/results/vt-object-hardware-plain-2-new" "$LAB/results/vt-object-software-plain-2-new")
python3 "$E/audit.py" --build "$B" --runs "${RUNS[@]}" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-object-audit-new.json"
python3 "$E/mutations.py" --build "$B" --runs "${RUNS[@]}" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-object-mutations-new"
```

The next investigation should trace the actual consumer and decision following
these natural object creations without inventing a resource or private video
command. The existence of these objects is not a working decoder or a Metal
feature extension.
