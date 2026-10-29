# VideoToolbox's device-registration call

In two observed hardware-required requests, VideoToolbox passes the dictionary
linked to the first enumerated GTX 880M device and its `RegistryID` lookup
result to a natural three-argument call. The destination pointer is non-null
and distinct from the device dictionary; the call returns normally in both
runs. The pinned call's static import is `CFDictionarySetValue`, and its live
slot resolves to that symbol when the debugger is armed.

This is evidence consistent with adding the device dictionary to another
dictionary under its registry-ID value. The target slot is sampled at arming,
not during the call, and the destination is not read back. The type or numeric
contents of the key and the later use or persistence of the destination are not
established. The observation does not prove decoder selection or explain the
public `-12906` failure; both observed requests still produce zero frames.

## Method and controls

The witness extends [the post-enumeration study](VIDEO_VT_ENUMERATION_DECISION.md).
It matches the first enumerated object to the unique `nvAccelerator` whose PCI
ancestor is `10de:1198`, verifies the device-dictionary identity and the
`RegistryID` lookup, and compares those pointers to the call's key and value
arguments. A later hardware breakpoint confirms return on the same thread.
No pointer or registry ID is emitted. The witness checks pinned code, key
constants and loaded import symbols before arming; it runs no debugger
expressions and issues no extra private video command. Debugger timing can
differ and the witness is confined to the test process.

A signed CPU fixture checks the same observer with correct arguments, wrong
key and wrong value, as well as zero/one enumeration, null creation, a wrong
target, a bad marker and both comparison branches. Two observed and two plain
hardware-required requests all fail with `-12906`. Two observed and two plain
software controls decode 24 frames matching 2,764,800 reference bytes, without
hitting the hardware-path witness points. The eight runs use distinct,
nonoverlapping cooperative reservations; debugger and target processes all
terminate. WindowServer is not excluded.

The [audit](video-vt-device-registration-validation.json) checks the static
import, code and source hashes, CPU controls, event identity and order, signed
builds, run receipts and software pixels. It verifies the expected
VideoToolbox diagnostic. Eight focused
[offline mutations](video-vt-device-registration-mutations.json) challenge the
new call arguments and prior identity/branch observations without GPU work.
Earlier mutation cohorts remain in their own reports. Three system files were
hashed before and after each run; the MetalOld file and display inventory were
checked at audit time. No system driver, framework, OCLP or firmware was
changed.

## Reproduction

Use the fixture/reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
pinned cache, cooperative lab reservation and fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_device_registration
C="$LAB/results/vt-registration-cal-new"
B="$LAB/results/vt-registration-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-registration-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-registration-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-registration-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-registration-mutations-new"
```

The next step is to observe a natural read of this destination and trace its
connection to decoder selection. This result is not a video-driver fix or a
performance claim.
