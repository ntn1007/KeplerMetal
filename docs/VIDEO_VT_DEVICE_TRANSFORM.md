# The next VideoToolbox call after GTX enumeration

In two instrumented, hardware-required session-creation attempts, the first
Metal enumeration item was the device linked to the selected GTX 880M
registry entry, as in [the earlier identity witness](VIDEO_VT_FIRST_DEVICE_IDENTITY.md).
The same device pointer was passed on the same thread to a natural direct call
within VideoToolbox. In each run that call returned a **non-null value**.
Both public requests nevertheless returned `-12906` and zero frames.

The call's target is VideoToolbox image offset `0x5fea84` on the pinned cache
profile. The audit verifies the caller's direct-call target and hashes the
bounded target region selected by `LC_FUNCTION_STARTS`; the debugger checks
both live code regions before arming. The exact source function name, return
type and meaning of the returned value are not established. A non-null return
is not proof that a decoder selected the device, that video resources were
created, or that hardware decoding occurred. The debugger observes only this
bounded path in the test process and may affect timing.

The host selects a unique `nvAccelerator` with PCI ancestor `10de:1198` and
passes its registry ID to a no-op marker. Hardware breakpoints and bounded
reads then compare the constructed device's registry ID, first list element,
and subsequent call argument, without logging the IDs or pointers. A return
breakpoint records only whether the value is null. The debugger does not
execute expressions, fabricate a video context or issue a private video
selector. Earlier breakpoints are disabled before later ones are armed, so the
witness stays within the host's hardware-breakpoint limit.

A signed CPU calibration exercises a one-item path, zero-item path, wrong
registry ID, bad marker and null return. The wrong ID is rejected and the null
return is distinguished from the non-null case. Two observed and two plain
hardware-required requests all fail with `-12906`. Two observed and two plain
software controls decode 24 frames matching 2,764,800 reference bytes; the
hardware-path witness points do not fire in the observed software controls.
The eight test runs use separate nonoverlapping cooperative reservations, and
all debugger and target processes terminate. WindowServer is not excluded.

[Audit](video-vt-device-transform-validation.json) checks the signed builds,
CPU calibration, static call target, live code checks reported by the debugger,
identity and event order, run receipts and software pixels. The expected
VideoToolbox diagnostic on the debugged hardware runs is checked explicitly.
Nine [offline mutations](video-vt-device-transform-mutations.json) reject
altered input, output and control evidence; they execute no GPU work. Three
system files were hashed before and after each run, while the MetalOld file
and GPU inventory were checked at audit time. No system driver, framework,
OCLP or firmware was modified.

## Reproduction

Use the fixture and reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md),
the pinned cache and cooperative reservation, and fresh output paths. Hardware
breakpoints can change timing.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_device_transform
C="$LAB/results/vt-transform-cal-new"
B="$LAB/results/vt-transform-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-transform-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-transform-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-transform-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-transform-mutations-new"
```

The next investigation is to identify the returned value and trace its use
through the following VideoToolbox decision. This result is not a video-driver
fix or a performance claim.
