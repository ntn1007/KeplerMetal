# AppleGVA cached-entry breakpoint: two bounded requests

Two separate H.264 hardware-required requests used the existing process-local
VideoToolbox dependency and board-policy counterfactuals. In each, a hardware
breakpoint at the pinned AppleGVA cached-entry first-byte check resolved but
reported **zero hits**. The property-return breakpoint hit once with a null
`IOGVACodec`, and the list-entry breakpoint hit twice; the observed list head
matched the recorded property node address. Each decoder request returned
`-12913` and zero images. Both target and debugger terminated and their
cooperative lab reservations reached terminal state.

This does not prove the cache path is impossible or that the node's lifetime
was continuous. Each request used a fresh process and one decoder request: it
does not test repeated sessions within the same process. A zero-hit breakpoint
does not validate the callback's live cache-field reader; two mock-process
CPU tests cover its handling of nonzero, zero, and unreadable bytes, but a
real-breakpoint cached-field calibration was **NOT RUN at the time of these
video trials**. A [subsequent CPU calibration](VIDEO_GVA_CACHE_READER_CALIBRATION.md)
exercised the same callback at four hardware-breakpoint hits. The hardware
breakpoint framework itself passed seven CPU-only processes and a reserved
CPU control. The debugger and counterfactuals can affect behavior. The
reservation coordinates participating laboratory runners, not arbitrary apps.

The marker verifies the image UUID and six loaded region hashes; LLDB also
verifies those regions before installing its breakpoints. The independent
[audit receipt](video-gva-cache-witness-validation.json) binds the inputs,
log hashes and terminal records. There is no driver, OCLP, firmware or system
change, and no hardware decoding or performance improvement is claimed.
The next informative experiment is two or more controlled session creations in
one process, with an actual cached-field breakpoint calibration and clear
per-request markers. It must preserve the same isolation and negative controls.

## Reproduction

Requires the retained private laboratory and its pinned base build. Use fresh
output paths and the shared cooperative GPU reservation. If a target or its
debugger remains unresolved, retain its reservation and inspect it instead of
starting another GPU cohort.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_cache_witness
B="$R/gva-property-build-20261028-01"
CAL="$R/cache-cal-new"
CTRL="$R/cache-control-new"
BUILD="$R/cache-build-new"
python3 "$E/cpu_calibration.py" --out "$CAL"
python3 "$E/reserved_cpu.py" --lab "$LAB" --calibration "$CAL" --out "$CTRL"
python3 "$E/build_gva.py" --lab "$LAB" --base "$B" --calibration "$CAL" --reserved-control "$CTRL" --out "$BUILD"
python3 "$E/run_gva.py" --lab "$LAB" --base "$B" --build "$BUILD" --out "$R/cache-current-1-new" --mode current --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$B" --build "$BUILD" --out "$R/cache-current-2-new" --mode current --witness on
python3 "$E/audit_gva.py" --base "$B" --build "$BUILD" --calibration "$CAL" --reserved-control "$CTRL" --runs "$R/cache-current-1-new" "$R/cache-current-2-new" --out "$R/cache-audit-new.json"
python3 -m unittest discover -s tests -p 'test_video_gva_cache_witness.py'
```
