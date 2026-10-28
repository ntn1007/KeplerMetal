# AppleGVA constructor returns in scoped debugger tests

In **two** counterfactual H.264 requests on the iMac, hardware breakpoints in
the target process recorded the instruction immediately following the base
initializer call and then the instruction immediately following the derived
constructor call. Both observations in each run have the same thread ID,
`r14 = 2`, matching loaded instruction bytes, and caller-frame image offsets
115492 and 264163 respectively. The debugger reported both locations as
hardware breakpoints. Together with the pinned call instructions, this shows
the base and derived constructors returned on these instrumented executions.

This qualifies the earlier static [constructor mapping](VIDEO_GVA_RTTI.md).
It does not read back the live object's vtable, prove general behavior of other
selectors, or demonstrate execution of the GTX video engine. The requests use
process-local `IOGVACodec` and board-policy substitutions; the debugger can
change timing. Both return **-12913 and zero images**, so the video failure
occurs despite reaching these points in these particular runs.

One wrong-board control armed the same witness but hit neither point and
returned -12906. One current-board control without the marker returned
-12913. One software control produced six images matching all 691,200 bytes of
the CPU reference. These are bounded controls; they do not establish complete
debugger transparency or all uninstrumented behavior. The CPU debugger
calibration also checks dynamic loading, hardware breakpoint hits, preserved
observed bytes, and refusal of a wrong base.

Every execution used the cooperative lab reservation. The runner waits for an
explicit debugger-observed target exit, confirms the debugger and target are
absent from the process table, and leaves the reservation unresolved if their
terminal outcome cannot be established. An unexpected stop remains under
debugger observation rather than triggering an automatic kill. The controlled
test host was separately signed with `get-task-allow`; system components and
the installed NVIDIA driver were not altered.

The [sanitized audit](video-gva-constructor-return-validation.json) binds the
five run receipts, build, signatures, CPU calibration, control logs and frame
comparisons. The original run receipts did not pin the runner source hash; the
runner source is published, but that specific historical provenance link is
not claimed. Raw logs, vendor bytes and binaries remain in the private lab.

## Reproduction on the qualified profile

Requires the retained lab fixtures and the shared reservation implementation;
all output paths must be new. If a process remains unresolved, retain the
reservation and inspect the existing debugger rather than restarting the test.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
EXP=bridge/experiments/video_gva_hw_witness
BASE="$R/gva-property-build-20261028-01"
CAL="$R/hw-calibration-new"
CONTROL="$R/hw-reserved-cpu-new"
BUILD="$R/hw-gva-build-new"
python3 "$EXP/cpu_calibration.py" --out "$CAL"
python3 "$EXP/reserved_cpu.py" --lab "$LAB" --calibration "$CAL" --out "$CONTROL"
python3 "$EXP/build_gva.py" --lab "$LAB" --base "$BASE" --calibration "$CAL" --reserved-control "$CONTROL" --out "$BUILD"
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/hw-cpu-new" --mode cpu --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/hw-current-1-new" --mode current --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/hw-wrong-new" --mode wrong --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/hw-current-off-new" --mode current --witness off
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/hw-current-2-new" --mode current --witness on
python3 "$EXP/audit_gva.py" --base "$BASE" --build "$BUILD" --calibration "$CAL" --reserved-control "$CONTROL" \
  --runs "$R/hw-cpu-new" "$R/hw-current-1-new" "$R/hw-wrong-new" "$R/hw-current-off-new" "$R/hw-current-2-new" \
  --out "$R/hw-audit-new.json"
```
