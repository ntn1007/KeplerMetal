# VideoToolbox's first reads from the GTX device dictionary

In two observed hardware-required requests, VideoToolbox reads two non-null
values from the same dictionary linked to the first enumerated GTX 880M device.
The pinned caller uses the keys `RegistryID` and `IORegistryName`. It passes
the second returned pointer and the constant `IGPU` to a comparison call;
the low byte of that call's return is zero in both runs.

The cache's static import metadata identifies the lookup as
`CFDictionaryGetValue` and the comparison as `FigCFEqual`. The live import
slots resolve to those symbols when the debugger is armed, and the live key
constants and caller code are checked. They are not checked again at the
instant of each call. The observations are consistent with the device name
not comparing equal to `IGPU`; the field's actual text and type were not read,
and the implementation of `FigCFEqual` was not independently qualified here.
The `RegistryID` value is non-null but its numeric contents are not validated.
These results do not prove that this comparison causes the failure or that a
decoder selects the GTX. Both public requests still return `-12906` and zero
frames.

## Method and controls

The witness extends [the dictionary-creation study](VIDEO_VT_DEVICE_DICTIONARY.md).
It matches the first Metal list item to the device with the selected NVIDIA
registry ID, follows the same pointer through the helper and verifies that its
return matches the observed dictionary-creation result. It then verifies the
same dictionary pointer across the two lookups and the second returned pointer
and key at the comparison input. The debugger observes registers and bounded
memory using hardware breakpoints; it does not execute expressions or add
video commands. Pointer values and registry IDs are not emitted. Prior
breakpoints are disabled before later ones are armed to respect the hardware
breakpoint limit.

A separate CPU fixture exercises one and zero items, a wrong device, a bad
marker, a null creation result, and both zero and one comparison returns.
The latter is a control for the witness, not a claim about VideoToolbox. Two
observed and two plain hardware-required sessions fail with `-12906`; two
observed and two plain software sessions produce 24 frames matching 2,764,800
reference bytes. The observed software controls do not hit the hardware-path
witness points. Eight runs use separate nonoverlapping cooperative reservations;
all debugger and target processes terminate. Debugging can change timing and
WindowServer is not excluded.

The [audit](video-vt-device-key-reads-validation.json) checks the signed
builds, CPU controls, static key constants and imports, loaded checks reported
by the debugger, same-thread identity chain, run receipts and software pixels.
The expected VideoToolbox diagnostic on the debugged hardware runs is checked.
Fifteen [offline mutations](video-vt-device-key-reads-mutations.json) challenge
the captured values and controls without running the GPU. Three system files
were hashed before and after each run; the MetalOld file and GPU inventory
were checked at audit time. No system driver, framework, OCLP or firmware was
changed.

## Reproduction

Use the fixture and reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
pinned cache and lab reservation, and fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_device_key_reads
C="$LAB/results/vt-keys-cal-new"
B="$LAB/results/vt-keys-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-keys-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-keys-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-keys-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-keys-mutations-new"
```

Next, qualify the value and trace the subsequent decision without assuming the
zero comparison is an error. No hardware-video execution or driver fix is
claimed.
