# Scoped witness for AppleGVA renderer classification

In two instrumented, hardware-required H.264 requests, a process-local
synthetic `IOGVACodec` string enabled the observed node's flag. Each request
then hit the pinned renderer-classification entry **twice**. At each hit, the
node field was `0x01040008` and its flags were `1,0,0,1`. The next relevant
breakpoint was the loop's skip instruction, on the same thread and with the
same pointer value and fields. The two caller offsets and order matched across
runs. The enumeration output remained zero; each VideoToolbox request returned
`-12913` with no frames.

This runtime sequence supports the earlier [static prediction](VIDEO_GVA_RENDERER_FILTER.md):
the observed identifier is outside both numeric categories in the pinned
selection-flag-zero path. The individual conditional branch instructions were
not stepped, and matching pointer values do not prove allocation lifetime or
object identity. The debugger can affect timing. These results do not establish
the entire cause of the VideoToolbox failure, the correct NVIDIA property, or
compatibility of a different identifier with the downstream provider. The
synthetic string is fabricated and is not a NVIDIA configuration value.
**No hardware video decoding is proved.**

With the string probe off, both list visits reached the skip instruction with
flag `0x463` equal to zero; neither reached the classification breakpoint. A
wrong-board control armed the marker without reaching the watched sites, while
a no-marker current-board control still returned `-12913`. A software-only
VideoToolbox control decoded six frames matching 691,200 CPU-reference bytes.
The CPU calibration uses original code and explicit register fixtures: an
excluded case hits classification and skip with the same pointer, an accepted
control omits skip, and an incorrect image base is refused. This calibrates the
witness; it does not execute or validate the proprietary classifier. A separate
reserved CPU calibration verifies the debugger's terminal handling.

An initial CPU calibration reported `KP_HW_ARM_FAIL target_bytes` while arming
the assembly-label fixture. The precise cause was not isolated. Both target and
debugger terminated, no video request was made in that attempt, and a fixture
with C++ functions was rebuilt in a fresh directory. All six qualified runs subsequently reached terminal
state under the cooperative reservation. That reservation covers participating
lab runners, not arbitrary system GPU use. The [sanitized audit](video-gva-classification-witness-validation.json)
binds the observations, controls and hashes. No system driver, framework, OCLP
or firmware was modified.

## Reproduction on the retained profile

Run from the repository root using the existing private lab artifacts. These
commands require a matching device and pinned system profile. Use fresh output
paths and run each command sequentially. If process termination cannot be
established, preserve the reservation and investigate before any retry.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_classification_witness
BASE="$R/gva-codec-probe-base-20261029-02/base"
C="$R/class-cal-new"
Q="$R/class-reserved-new"
B="$R/class-build-new"
python3 "$E/cpu_calibration.py" --out "$C"
python3 "$E/reserved_cpu.py" --lab "$LAB" --calibration "$C" --out "$Q"
python3 "$E/build_gva.py" --lab "$LAB" --base "$BASE" --calibration "$C" --reserved-control "$Q" --out "$B"
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/class-cpu-new" --mode cpu --witness on --probe off
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/class-off-new" --mode current --witness on --probe off
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/class-synth1-new" --mode current --witness on --probe synthetic
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/class-synth2-new" --mode current --witness on --probe synthetic
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/class-wrong-new" --mode wrong --witness on --probe off
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/class-no-witness-new" --mode current --witness off --probe off
python3 "$E/audit.py" --base "$BASE" --build "$B" --calibration "$C" --reserved-control "$Q" \
 --region "$R/video-gva-session-enumeration-inner-20261018/function-region.private.bin" \
 --prior-audit "$R/gva-renderer-filter-audit-20261029-01.json" \
 --runs "$R/class-cpu-new" "$R/class-off-new" "$R/class-synth1-new" "$R/class-synth2-new" "$R/class-wrong-new" "$R/class-no-witness-new" --out "$R/class-audit-new.json"
```
