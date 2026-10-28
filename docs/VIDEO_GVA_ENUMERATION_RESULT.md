# AppleGVA enumeration output in scoped video tests

In two counterfactual H.264 requests, a hardware breakpoint immediately after
the AppleGVA routine at image offset 146236 read **zero** from its 32-bit
output field. The preceding two breakpoints observed the base and derived
constructor returns in the same thread with `r14 = 2`; caller-frame offsets
matched the pinned dispatch path. Both requests returned **-12913 with zero
images**.

The observed loaded caller passes the address held in `rbx` to that routine.
The separately verified loaded callee computes `(end - begin) >> 3` and stores
the result through that output pointer. Therefore, in these executions the
routine reports a list length of zero. The meaning of every possible list
entry and why this list is empty are **not established**. The following pinned
caller code compares this field with zero, but this experiment did not directly
observe its final return value. The empty list is a lead, not yet a demonstrated
root cause of the VideoToolbox error or a hardware decoding result.

The own-process marker checks the live image UUID; both it and the debugger
check four loaded code-region hashes before arming. The debugger reads four bytes from
the stopped process using LLDB; the target does not dereference a new pointer
for the observer. A CPU-only calibration verifies three hardware breakpoints,
reads the known value 7 from the controlled register, and refuses an unreadable
address. The debugger may affect timing. A wrong-board control armed the marker
but did not reach the three watched points; a current-board run without the
marker still returned -12913. The software control produced six frames matching
691,200 CPU-reference bytes.

The [audit receipt](video-gva-enumeration-validation.json) binds the five run
receipts, pinned static call and count instructions, loaded-code hashes, signed
artifacts, CPU controls and software frames. As in the prior cohort, the
original run receipts do not record a hash of the runner source. The tests use
process-local property and board-policy substitutions, and do not modify the
installed driver, OCLP or system files. See the earlier
[constructor-return evidence](VIDEO_GVA_CONSTRUCTOR_RETURN.md).

## Reproduction

Requires the exact qualified profile, previously captured private code regions,
retained lab fixtures and the cooperative GPU reservation. Use new output
paths. If a process remains unresolved, keep the reservation and inspect that
debugger; do not restart a potentially live session.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
EXP=bridge/experiments/video_gva_enumeration_witness
BASE="$R/gva-property-build-20261028-01"
CAL="$R/enum-calibration-new"
CONTROL="$R/enum-reserved-cpu-new"
BUILD="$R/enum-build-new"
python3 "$EXP/cpu_calibration.py" --out "$CAL"
python3 "$EXP/reserved_cpu.py" --lab "$LAB" --calibration "$CAL" --out "$CONTROL"
python3 "$EXP/build_gva.py" --lab "$LAB" --base "$BASE" --calibration "$CAL" --reserved-control "$CONTROL" --out "$BUILD"
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/enum-cpu-new" --mode cpu --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/enum-current-1-new" --mode current --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/enum-wrong-new" --mode wrong --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/enum-off-new" --mode current --witness off
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/enum-current-2-new" --mode current --witness on
python3 "$EXP/audit_gva.py" --base "$BASE" --build "$BUILD" --calibration "$CAL" --reserved-control "$CONTROL" \
  --dispatch-region "$R/video-gva-provider-session-20261018/function-region.private.bin" \
  --enumerator-region "$R/gva-post-constructor-20261029-01/function-region.private.bin" \
  --runs "$R/enum-cpu-new" "$R/enum-current-1-new" "$R/enum-wrong-new" "$R/enum-off-new" "$R/enum-current-2-new" \
  --out "$R/enum-audit-new.json"
```
