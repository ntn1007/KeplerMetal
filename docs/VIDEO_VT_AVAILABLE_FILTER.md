# GTX entry reaches a VideoToolbox request filter

In two instrumented hardware-required H.264 requests, the availability array
previously traced to the GTX contains one entry when the caller asks for its
count. The caller retrieves index zero; its returned pointer matches the
previously followed GTX-linked dictionary. The same dictionary is passed to a
local VideoToolbox function with a non-null request argument and a null third
argument. Its return byte is `0` in both requests. Static code at the caller
checks that byte before conditionally adding a registry value to a second
array; the branch itself was not separately observed. The request object's
meaning and the cause of the zero remain unknown.

The observation uses same-thread and caller-frame identity, bounded read-only
register and stack reads, and hardware breakpoints retired as the trace
progresses. Array count and index calls are identified through pinned static
imports, but their live bindings were not checked at their call instants. The
local filter call target is pinned by static code; its live body was not
independently checked here. Pointers and registry IDs are not published.
Debugging can affect timing.

A separate static inspection of the pinned filter function identifies
references to `PresentIORegKeysAndValues`, `AbsentIORegKeys` and `Service`.
The runtime path through these keys was not observed, so none is established as
the reason for the result. The filter return is one local decision, not proof
that it alone causes `-12906`, nor that the dedicated video engine executed.

Two observed and two plain hardware-required requests return `-12906` with
zero frames. Two observed and two plain software controls decode 24 frames
matching 2,764,800 reference bytes. The 14 CPU calibration cases include wrong
entry, rejected filter, wrong output, wrong key/value, unavailable and other
entry controls. All eight real runs have nonoverlapping cooperative GPU
reservations and terminated processes. Three system files were hashed around
each run; the MetalOld file and display inventory were checked at audit time.

The [audit](video-vt-available-filter-validation.json) pins both function
regions and the relevant call targets, checks calibration, event identities,
ordering, terminal receipts and software output. [Offline mutations](video-vt-available-filter-mutations.json)
challenge those checks without executing a GPU workload. No system component,
OCLP or firmware was modified.

## Reproduction

Use the fixture/reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
pinned cache and common cooperative lab reservation, with fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_available_filter
C="$LAB/results/vt-filter-cal-new"
B="$LAB/results/vt-filter-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-filter-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-filter-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-filter-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-filter-mutations-new"
```

Next, trace the filter's internal key lookups and its exit path in the same
process. This evidence is not a driver fix or a performance claim.
