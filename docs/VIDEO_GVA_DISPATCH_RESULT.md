# Scoped AppleGVA enumeration and dispatch result

Two separately launched H.264 hardware-required requests reached the same
pinned AppleGVA dispatch sequence. In each process, three hardware breakpoints
recorded, on the same thread, the base constructor return, a zero enumeration
count, and then **`EAX = 1`** at the instruction immediately after the
zero-count comparison and `setz`, before the dispatch epilogue. The pinned
instruction bytes agree with that interpretation. The two requests each ended
with VideoToolbox status **-12913 and zero output images**.

This extends the [prior zero-count witness](VIDEO_GVA_ENUMERATION_RESULT.md):
the earlier run did not observe the dispatch result register. The new witness
does not observe the caller receiving the value or demonstrate how it becomes
the public error. It does not identify what all list entries mean, prove the
complete cause of the failure, or establish video-engine execution. Both
hardware requests use the already documented process-local synthetic property
presence and board-policy substitutions. The debugger can change timing; no
property or board-policy substitution was applied globally.

The wrong-board control returned -12906 without hitting the three sites; an
otherwise equivalent current-board request without the marker still returned
-12913. One software control produced six frames matching 691,200 bytes of the
retained CPU reference. A separate CPU calibration observed both known return
register values 0 and 1, refused an incorrect image base and handled an
unreadable pointer. The shared reservation was used for each video host; all
five hosts and debuggers reached terminal state. This is not a performance
benchmark or a claim that the installed driver was modified.

## Evidence and reproduction

The [auditor](../bridge/experiments/video_gva_dispatch_result/audit_gva.py)
binds source, build, receipts, loaded code hashes, signatures, same-thread
stops and software pixel comparisons. A copied run with its observed result
changed to zero was rejected even after its log hash was updated. [Sanitized
receipt](video-gva-dispatch-result-validation.json).
Vendor binaries and raw captures remain in the private lab. All paths below
must be fresh and the shared reservation must be resolved before each run.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_dispatch_result
BASE="$R/gva-property-build-20261028-01"
C="$R/dispatch-result-cal-new"
CTRL="$R/dispatch-result-control-new"
B="$R/dispatch-result-build-new"
python3 "$E/cpu_calibration.py" --out "$C"
python3 "$E/reserved_cpu.py" --lab "$LAB" --calibration "$C" --out "$CTRL"
python3 "$E/build_gva.py" --lab "$LAB" --base "$BASE" --calibration "$C" --reserved-control "$CTRL" --out "$B"
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/dispatch-cpu-new" --mode cpu --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/dispatch-current-1-new" --mode current --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/dispatch-wrong-new" --mode wrong --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/dispatch-off-new" --mode current --witness off
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/dispatch-current-2-new" --mode current --witness on
python3 "$E/audit_gva.py" --base "$BASE" --build "$B" --calibration "$C" --reserved-control "$CTRL" \
  --dispatch-region "$R/video-gva-provider-session-20261018/function-region.private.bin" \
  --enumerator-region "$R/gva-post-constructor-20261029-01/function-region.private.bin" \
  --runs "$R/dispatch-cpu-new" "$R/dispatch-current-1-new" "$R/dispatch-wrong-new" "$R/dispatch-off-new" "$R/dispatch-current-2-new" \
  --out "$R/dispatch-result-audit-new.json"
```

The next investigation is the actual caller's handling of this value and its
relation to the hardware provider. The value `1` is not assigned a semantic
error name without additional evidence.
