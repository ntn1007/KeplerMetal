# AppleGVA free binding and CPU interposition control

A process-local experimental library observes calls to public `free` and
`malloc_zone_free` when their pointer matches an explicitly armed address. In
**two CPU-only processes**, an independently built caller library freed a
watched allocation through each interface. Both positive controls were
observed; an unrelated pointer, a null arm, duplicate arm and non-owner disarm
were rejected or excluded as expected. The original functions were called.
These tests establish behavior for the synthetic caller, not universal
interposition coverage.

In two current-board H.264 processes and one wrong-board control, LLDB read the
live slot used by the previously mapped AppleGVA `free` callsite while the
validated image was armed. In all three, its value matched the experimental
`observed_free` function. The audit checks the pinned static call-to-stub
mapping and slot offset. This is evidence for **that particular binding at
that observation time**, not for every possible deallocator or later rebinding.
The watched pointer was **not armed in these video runs**, so the experiment
does not measure node frees or prove that an allocation survived.

A software control produced 18 reference-matching frames; a current-board
control without the injected observer and both instrumented current-board
runs returned `-12913` for all three hardware-required requests, with zero
images. The wrong-board process returned `-12906`. These are process-local
counterfactual tests; debugger timing and injection can change behavior. No
system driver, OCLP or firmware changed. No GPU video execution or performance
gain is claimed.

The [sanitized receipt](video-gva-heap-binding-validation.json) binds the
static region, CPU control sources, signed library and terminal process logs.
The next experiment must safely connect the observed node address to the
watcher, calibrate that connection with actual matching and nonmatching frees,
and explicitly account for unobserved allocator interfaces and intervals.

## Reproduction

Requires the prior private request-witness build and its integrated base,
pinned AppleGVA capture and the cooperative laboratory reservation. Use fresh
paths. Never retry while a debugger or target remains unresolved.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
H=bridge/experiments/video_gva_heap_watch
E=bridge/experiments/video_gva_heap_binding
I="$R/gva-repeat-integrated-20261029-01"
P="$R/gva-request-build-20261029-02"
C="$R/heap-cal-new"
B="$R/heap-binding-build-new"
python3 "$H/calibrate.py" --out "$C"
python3 "$E/build.py" --lab "$LAB" --parent "$P" --heap-calibration "$C" --out "$B"
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-cpu-new" --mode cpu --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-wrong-new" --mode wrong --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-off-new" --mode current --witness off
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-on1-new" --mode current --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-on2-new" --mode current --witness on
python3 "$E/audit.py" --base "$I/base" --build "$B" --heap-calibration "$C" \
 --region "$R/gva-stack-caller-20261028-01/function-region.private.bin" --mapping "$R/gva-stack-caller-stubs-20261028-01.json" \
 --metadata "$R/gva-stack-caller-20261028-01/metadata.json" \
 --runs "$R/heap-cpu-new" "$R/heap-wrong-new" "$R/heap-off-new" "$R/heap-on1-new" "$R/heap-on2-new" --out "$R/heap-binding-audit-new.json"
```
