# VideoToolbox's post-enumeration branch

In two observed hardware-required session-creation attempts on the pinned
GTX 880M profile, VideoToolbox enumerated a first batch of one item, matched
that item to the selected NVIDIA device, and read the linked dictionary as in
[the earlier key-read witness](VIDEO_VT_DEVICE_KEY_READS.md). The comparison
call with `IGPU` returned zero. A subsequent enumeration call returned zero
for the same list; the later branch tested a zero flag matching the comparison
return and execution reached the branch's zero destination.

These observations are consistent with that enumeration yielding only the
one observed GTX-linked item and then taking the non-`IGPU` branch. The
fast-enumeration dispatch and comparison import targets are checked when the
debugger is armed, not at each call; concurrent list mutation and other
processes are not fully covered. The actual name value and comparison
implementation were not independently validated. The branch's later effect
is not established: it must not be described as the cause of `-12906`, a
successful decoder selection, or hardware video execution. Both observed
public requests still returned `-12906` and zero frames.

The witness uses hardware breakpoints and bounded process-local reads. The
identity chain and live code checks follow the earlier study. It verifies the
first and subsequent enumeration results against the same saved list, then
records the flag and destination. Prior breakpoints are disabled before later
ones are armed; no debugger expression or extra private video command is
executed. Debugger timing may differ from ordinary operation and WindowServer
is not excluded.

A signed CPU fixture exercises one and zero first-batch results, a wrong target,
a bad marker, a null helper return, and both comparison/branch outcomes.
Two observed and two plain hardware-required requests fail with `-12906`. Two
observed and two plain software controls decode 24 frames matching 2,764,800
reference bytes; the hardware-path witness points are absent in the observed
software runs. The eight runs use separate nonoverlapping cooperative
reservations and all debugger and target processes terminate.

The [audit](video-vt-enumeration-decision-validation.json) checks the cached
branch instructions and key imports, signed builds, CPU controls, live checks
reported by the debugger, same-thread observations, run receipts and pixels.
Eight focused [offline mutations](video-vt-enumeration-decision-mutations.json)
challenge the new decision and identity observations without executing GPU
work; earlier mutation cohorts remain in their own reports. The expected
VideoToolbox diagnostic is checked. Three system files were hashed before and
after each run; the MetalOld file and GPU inventory were checked at audit time.
No system driver, framework, OCLP or firmware was changed.

## Reproduction

Use the fixture/reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
pinned cache and lab reservation, and fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_enum_decision
C="$LAB/results/vt-decision-cal-new"
B="$LAB/results/vt-decision-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-decision-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-decision-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-decision-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-decision-mutations-new"
```

The next step is to follow the zero branch to the actual decoder-selection or
failure boundary, using separate controls. This is an observation, not a
driver fix or a performance result.
