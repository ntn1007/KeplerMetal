# VideoToolbox availability array at the output slot

Two observed hardware-required requests follow the GTX-linked dictionary through
VideoToolbox's availability traversal. The callback passes that dictionary and
its context to an append call. Later, in the same thread and stack frame, the
same context pointer is written to the helper's non-null output slot. A read of
that slot immediately after the write matches the context; the register used
by the pinned helper to set its status contains zero. The parent frame's sampled
PC belongs to VideoToolbox at image offset `0x3ffe` in both observations.

This is a process-local debugger observation at the write, not a read of the
returned array after the helper exits. Other entries may have been added or the
array changed later. Neither the caller's subsequent use, decoder selection,
nor hardware video execution is established. All four hardware-required
requests returned `-12906` and produced no frames. Debugging may change timing.

The pinned function's live bytes and the cache image are checked; imported
function bindings are checked at witness arming, not at the call instants.
Pointer comparisons occur inside LLDB; raw pointers and registry IDs are not
published. Hardware breakpoints are retired during the observation. The
12-case CPU calibration includes a wrong output pointer, wrong key/value,
unavailable and other-entry cases; all targets terminated. No private video
command or debugger expression is executed.

Two observed and two plain software requests produced 24 frames matching
2,764,800 reference bytes. The four hardware and four software processes used
separate nonoverlapping cooperative GPU reservations and signed immutable
clients. The [audit](video-vt-available-output-validation.json) checks the
pinned static profile, calibration, same-thread/frame observations, output
slot, order, reservations and software bytes. The [offline mutation
checks](video-vt-available-output-mutations.json) test altered logs without
running a GPU workload. Three system files were hashed around each run; the
MetalOld file and display inventory were checked during audit. No system
component, OCLP or firmware was modified.

## Reproduction

Use the fixture/reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
pinned cache and common cooperative lab reservation, with fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_available_output
C="$LAB/results/vt-output-cal-new"
B="$LAB/results/vt-output-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-output-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-output-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-output-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-output-mutations-new"
```

Next, inspect the caller at the observed offset and identify whether and how it
consumes the returned array. This evidence is not a driver fix or a performance
claim.
