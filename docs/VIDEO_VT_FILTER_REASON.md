# VideoToolbox request filter: observed lookup path

Two instrumented hardware-required H.264 requests follow the previously
identified GTX-linked dictionary into the VideoToolbox request filter. In the
same filter frame and thread, the first dictionary lookup uses the verified
`PresentIORegKeysAndValues` key and returns null. The next statically identified
lookup for `AbsentIORegKeys` also returns null. The subsequent call at the
statically identified `FigCFDictionaryGetInt64IfPresent` site returns a nonzero
byte for the `Service` lookup. A call at the statically identified
`IORegistryEntrySearchCFProperty` site then returns a null pointer, followed by
the filter's zero return byte.

The loaded filter body and key constants are checked at witness arming. The
`CFDictionaryGetValue` import is verified at arm time; the service and property
lookup imports are identified from the pinned cache, but their live bindings
are not independently checked. The observations are at the caller sites after
return, not independent observations inside the library callees. They do not
establish which IORegistry property was requested, why the call returned null,
whether a later stage independently rejects hardware video, or whether this
condition alone causes `-12906`. No dedicated video engine execution is proved.
Debugger timing can differ from normal execution.

The [CPU calibration](video-vt-filter-reason-validation.json) covers 18 cases,
including cache hits and misses, an absence-list hit, absent service and failed
property search, as well as wrong entry and prior traversal controls. Two
instrumented and two plain hardware-required requests all return `-12906`
without frames. Two instrumented and two plain software controls produce 24
frames matching 2,764,800 reference bytes. Eight processes use nonoverlapping
cooperative GPU reservations and terminate. The [audit](video-vt-filter-reason-validation.json)
checks the cache, live-profile receipt, same-frame chain, CPU controls and
software outputs; [offline mutations](video-vt-filter-reason-mutations.json)
challenge the audit without GPU work. Three system files were hashed around
each run, and MetalOld and display inventory were checked at audit time.
No system component, OCLP or firmware was changed.

## Reproduction

Use the fixture/reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
pinned cache and common cooperative lab reservation, with fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_filter_reason
C="$LAB/results/vt-reason-cal-new"
B="$LAB/results/vt-reason-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-reason-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-reason-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-reason-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-reason-mutations-new"
```

Next, determine the request property and the actual live call bindings, then
compare the service's real properties and selection flow. This is not a
driver fix or a performance claim.
