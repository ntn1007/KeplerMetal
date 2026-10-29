# Repeated H.264 requests with both experimental observers

The repeatable metadata and dependency observers are now linked into one
isolated, signed laboratory client. In two fresh-process CPU runs the client
created **three sequential software sessions each**. All 36 decoded frames
matched 4,147,200 bytes from the CPU reference. Every request has a separate
metadata and dependency record; all were complete, drained, and had valid
public controls. The test seam was absent from the linked dependency library.

A further four fresh processes requested three hardware-required sessions
each. Three current-board processes returned `-12913` for all nine requests;
a wrong-board control returned `-12906` for all three. No hardware images were
produced. These runs used the existing process-local VideoToolbox dependency
and board-policy counterfactuals, not a system-wide modification.

In each of two current-board debugger runs, the pinned breakpoint after the
`IOGVACodec` call hit once and returned null. The list-selection breakpoint
hit four times, while the resolved cached-entry first-byte breakpoint had
**zero hits**. The first dependency record reports one presence substitution;
subsequent records report none. These are observations in the tested
processes, not proof that the cache path is universally unreachable. The
host's request markers and debugger observations are in separate streams, so
individual list hits are **not assigned to particular requests**. Address
matches do not prove allocation lifetime or that a later node is the same
object. The debugger may change timing.

All six target and debugger processes terminated, and all reservations reached
terminal state without a kill request. The original pilot's standalone
concurrency tests remain separate from this integrated test: arbitrary client
concurrency, broader driver profiles and all failure paths are not qualified.
The [audit receipt](video-gva-repeat-integrated-validation.json) binds the
exact source and lab inputs, tests frame files and records, and verifies that
the CPU-only test seam is absent from the integrated library. No GPU video
execution, driver upgrade or performance gain is demonstrated; no system or
OCLP component was modified.

The next useful investigation is to identify why subsequent requests reach
list selection without a new observed property return, using per-request
synchronized markers and a bounded object-lifetime witness. Do not invent an
NVIDIA codec value or infer successful decoding from list reuse.

## Reproduction

Requires the retained pinned private laboratory, the two CPU prototype
qualification directories, the earlier diagnostic build, and the shared
cooperative GPU reservation. Use new output names and wait for terminal state
before each run. If a debugger or target remains unresolved, retain the
reservation and investigate rather than restarting.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_repeat_sessions
OLD="$R/gva-property-build-20261028-01"
W="$R/gva-cache-hw-build-20261029-01"
DIAG="$R/gva-repeat-diagnostic-build-20261029-01"
I="$R/repeat-integrated-new"
python3 "$E/build_integrated.py" --lab "$LAB" --base "$OLD" --witness-build "$W" --diagnostic-build "$DIAG" --out "$I"
RUN=bridge/experiments/video_gva_cache_witness/run_gva.py
python3 "$RUN" --lab "$LAB" --base "$I/base" --build "$I/build" --out "$R/repeat-cpu-on-new" --mode cpu --witness on
python3 "$RUN" --lab "$LAB" --base "$I/base" --build "$I/build" --out "$R/repeat-cpu-off-new" --mode cpu --witness off
python3 "$RUN" --lab "$LAB" --base "$I/base" --build "$I/build" --out "$R/repeat-current-off-new" --mode current --witness off
python3 "$RUN" --lab "$LAB" --base "$I/base" --build "$I/build" --out "$R/repeat-wrong-new" --mode wrong --witness on
python3 "$RUN" --lab "$LAB" --base "$I/base" --build "$I/build" --out "$R/repeat-current-on-1-new" --mode current --witness on
python3 "$RUN" --lab "$LAB" --base "$I/base" --build "$I/build" --out "$R/repeat-current-on-2-new" --mode current --witness on
python3 "$E/audit_integrated.py" --base "$I/base" --build "$I/build" \
  --metadata-qualification "$R/gva-repeat-metadata-qualify-20261029-03" \
  --dependency-qualification "$R/gva-repeat-dependency-qualify-20261029-01" \
  --runs "$R/repeat-cpu-on-new" "$R/repeat-cpu-off-new" "$R/repeat-current-off-new" \
         "$R/repeat-wrong-new" "$R/repeat-current-on-1-new" "$R/repeat-current-on-2-new" \
  --out "$R/repeat-integrated-audit-new.json"
```
