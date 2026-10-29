# The GTX entry in VideoToolbox's availability traversal

In two observed hardware-required requests, VideoToolbox traverses the same
destination to which it previously passed the GTX-linked dictionary and its
registry key. The traversal callback receives the same key, device dictionary
and context pointers. After the callback's `Available` lookup, its output
byte is `1`; the callback then passes the same device dictionary and context to
an append call, which returns normally.

The pinned static imports identify the traversal, boolean lookup and append as
`CFDictionaryApplyFunction`, `FigCFDictionaryGetBooleanIfPresent` and
`CFArrayAppendValue`. The loaded slots resolve to those symbols when the
witness is armed, but are not rechecked at the call instants. Under that
binding, the evidence shows the GTX-linked entry is encountered as available
and passed to the availability array. It does **not** establish the final
array's contents or lifetime, decoder selection, video-engine execution, or the
cause of `-12906`. Both observed requests still fail and produce zero frames.

The witness extends [the device-registration call study](VIDEO_VT_DEVICE_REGISTRATION_CALL.md).
It compares pointers only inside the debugger: registry ID, device dictionary,
traversal destination, callback context and append arguments are not emitted.
It verifies the callback frame when attributing the boolean and append. No
extra private video command or debugger expression is executed. Hardware
breakpoints are retired as the observation progresses; debugging may alter
timing and the process-local observation does not exclude WindowServer.

An initial exploratory GPU run saw additional append calls; those are not
attributed to the GTX. The revised witness retires its matched breakpoints and
has CPU controls for a distinct subsequent entry, including a case where the
GTX-like entry is unavailable and only the other entry is appended. It also
checks wrong key, wrong value, null and both comparison branches. An initial
CPU verification had a faulty log pattern; its completed logs and signed host
were copied unchanged to a fresh calibration directory, source hashes and
signature were checked, and the corrected verifier accepted them without
rerunning those CPU cases.

Two observed and two plain hardware-required requests all return `-12906`.
Two observed and two plain software controls decode 24 frames matching
2,764,800 reference bytes; the hardware-path points are absent in the observed
software controls. The eight runs use separate, nonoverlapping cooperative
reservations; debugger and target processes all terminate.

The [audit](video-vt-available-path-validation.json) checks the static callback
and imports, key constant, signed build, CPU controls, same-thread and frame
identity, event order, receipts and software pixels. Eight focused
[offline mutations](video-vt-available-path-mutations.json) challenge this
path without GPU work; earlier mutation cohorts remain in their own reports.
The expected VideoToolbox diagnostic is checked. Three system files were hashed
before and after each run; the MetalOld file and display inventory were checked
at audit time. No system driver, framework, OCLP or firmware was changed.

## Reproduction

Use the fixture/reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
pinned cache and cooperative lab reservation, and fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_available_path
C="$LAB/results/vt-available-cal-new"
B="$LAB/results/vt-available-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-available-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-available-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-available-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-available-mutations-new"
```

Next, follow the output array to the caller and determine which later selection
or capability test rejects the hardware request. This result is not a driver
fix or a performance claim.
