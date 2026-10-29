# Dictionary creation in the VideoToolbox device path

For two instrumented hardware-required VideoToolbox requests, the naturally
constructed Metal object linked to the selected GTX 880M enters the helper
studied in [VIDEO_VT_DEVICE_TRANSFORM.md](VIDEO_VT_DEVICE_TRANSFORM.md). The
helper returns the same non-null pointer observed immediately after its
internal creation call on the same thread.

On the pinned cache image, that internal call targets the import stub for
`CFDictionaryCreateMutable`. Before the test call, the debugger verifies that
the loaded stub's slot resolves to the `CFDictionaryCreateMutable` symbol in
CoreFoundation. The live VideoToolbox caller and helper instruction regions
are hashed before arming. Thus the result is strong evidence that the helper
returns the dictionary created for the device. The slot is checked at arming,
**not at the instant of the creation call**; a change in between is not ruled
out. No dictionary contents or later decoder selection are established.

The observer follows the first enumeration item and matches its pointer to the
Metal device whose registry ID matches the unique `nvAccelerator` with PCI
ancestor `10de:1198`. Hardware breakpoints then observe the helper input,
creation return and helper return. Pointers and registry IDs are compared in
the debugger and not emitted. The debugger runs no expressions, adds no video
selector and creates no synthetic video context. Prior breakpoints are
disabled before later ones are armed. This is a process-local witness and
its timing may differ from an unobserved run.

A separate signed CPU calibration checks one and zero items, wrong target,
wrong marker, null creation and matching creation/return pointers. Two
observed and two plain hardware-required requests all return `-12906` and zero
frames. Two observed and two plain software controls decode 24 frames matching
2,764,800 reference bytes; the hardware-path points do not fire in the observed
software controls. Eight serialized runs use separate cooperative reservations
and all debugger and target processes terminate. WindowServer is not excluded.

The [audit](video-vt-device-dictionary-validation.json) checks the static
creation import, pinned code, signed builds, calibration, same-thread pointer
comparisons, run receipts and software pixels. The expected diagnostic on the
debugged hardware runs is also verified. Eleven
[offline mutations](video-vt-device-dictionary-mutations.json) challenge the
observation and controls; they execute no GPU work. Three system files were
hashed before and after each run, while the MetalOld file and display
inventory were checked at audit time. No system driver, framework, OCLP or
firmware was changed.

## Reproduction

Use the fixture and reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md),
the pinned cache profile and lab reservation; use fresh output paths.
Hardware breakpoints may affect timing.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_device_dictionary
C="$LAB/results/vt-dictionary-cal-new"
B="$LAB/results/vt-dictionary-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-dictionary-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-dictionary-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-dictionary-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-dictionary-mutations-new"
```

Next, inspect which bounded fields the caller reads and how those values affect
the decoder decision, with independent controls. This result does not
constitute hardware video execution or a driver fix.
