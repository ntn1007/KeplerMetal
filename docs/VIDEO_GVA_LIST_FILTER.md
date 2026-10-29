# AppleGVA list filter in scoped video tests

Two instrumented H.264 requests each reached the pinned list-selection routine
with selector 2, selection flag 0 and a non-null initial list head. A bounded
read while the process was stopped found **one** entry and a null next link.
Its observed 32-bit field was `0x01040008`; bytes at offsets `0x460` through
`0x463` were respectively `1, 0, 0, 0`. In the same thread, the later
enumeration output was zero. Both requests returned -12913 and no images.

The loaded, hash-checked selection instructions follow the flag-zero path
and skip an entry when byte `0x461` is nonzero or byte `0x463` is zero. Thus,
**if the observed entry remains unchanged when execution resumes and the
pinned normal control flow applies**, its zero byte at `0x463` explains why
this one-entry snapshot would contribute no selection. The exact branch was
not separately traced, and the byte's meaning and the reason it is zero remain
unknown. The snapshot does not establish what the list would contain in other
applications or configurations.

The observed numeric field equals the `IOVARendererID` value separately read
from the `nvAccelerator` registry entry in these processes. This is a numeric
match only: it does **not** establish that the list entry and registry object
are the same object, or prove that a decoder or hardware provider is absent.
No hardware decoding or system-wide fix is claimed.

The witness reads at most 16 entries through LLDB, never writes their memory,
and reports a cycle, limit or failed read rather than continuing indefinitely.
A CPU-only control verifies two synthetic entries, a null head, a cycle and an
unreadable output address. The marker and debugger independently validate five
loaded code-region hashes; the marker also verifies the image UUID. A wrong
board control, a run without the marker and a six-frame CPU reference control
are included. The test requests use process-local property and board-policy
substitutions and the debugger may affect timing.

The [sanitized audit](video-gva-list-validation.json) binds the run and runner
hashes, loaded and static code checks, CPU controls and reference frames. The
derived constructor return was directly observed; the earlier base return is
inferred from the verified call flow in this cohort. No installed driver,
OCLP, firmware or system file was changed. The preceding result is documented
in [VIDEO_GVA_ENUMERATION_RESULT.md](VIDEO_GVA_ENUMERATION_RESULT.md).

## Reproduction

Requires the exact retained private lab, the captured static regions and the
cooperative GPU reservation. Use fresh output paths; keep the existing
reservation if a debugger or its child remains unresolved.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
EXP=bridge/experiments/video_gva_list_witness
BASE="$R/gva-property-build-20261028-01"
CAL="$R/list-calibration-new"
CONTROL="$R/list-reserved-cpu-new"
BUILD="$R/list-build-new"
python3 "$EXP/cpu_calibration.py" --out "$CAL"
python3 "$EXP/reserved_cpu.py" --lab "$LAB" --calibration "$CAL" --out "$CONTROL"
python3 "$EXP/build_gva.py" --lab "$LAB" --base "$BASE" --calibration "$CAL" --reserved-control "$CONTROL" --out "$BUILD"
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/list-cpu-new" --mode cpu --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/list-current-1-new" --mode current --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/list-wrong-new" --mode wrong --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/list-off-new" --mode current --witness off
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/list-current-2-new" --mode current --witness on
python3 "$EXP/audit_gva.py" --base "$BASE" --build "$BUILD" --calibration "$CAL" --reserved-control "$CONTROL" \
  --dispatch-region "$R/video-gva-provider-session-20261018/function-region.private.bin" \
  --enumerator-region "$R/gva-post-constructor-20261029-01/function-region.private.bin" \
  --inner-region "$R/video-gva-session-enumeration-inner-20261018/function-region.private.bin" \
  --runs "$R/list-cpu-new" "$R/list-current-1-new" "$R/list-wrong-new" "$R/list-off-new" "$R/list-current-2-new" \
  --out "$R/list-audit-new.json"
```
