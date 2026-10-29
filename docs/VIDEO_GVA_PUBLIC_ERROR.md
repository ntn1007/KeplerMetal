# AppleGVA error observed at the VideoToolbox call boundary

Two instrumented hardware-required H.264 requests reached the previously
observed AppleGVA conditional exit. In each, the same thread then had
**`-12913` in the return register at the AppleGVA epilogue** and, immediately
after the corresponding indirect call in VideoToolbox, again had **`-12913`**.
At the AppleGVA stop, LLDB's caller frame pointed to that exact VideoToolbox
post-call address. Both public decoder-creation calls also returned `-12913`
and produced no images.

The pinned AppleGVA region contains an assignment of `-12913` on this exit
path; the pinned VideoToolbox bytes contain an indirect call immediately
before the observed post-call instruction. The marker and debugger checked
the loaded AppleGVA region; the debugger separately checked VideoToolbox's
UUID and its 2,061-byte live code hash before arming. This binds the observed
return across the call boundary more closely than merely comparing public
statuses. It does not trace every intervening operation or establish that all
other `-12913` errors have this cause. No provider execution or hardware
video decoding is demonstrated.

The two requests retain process-local synthetic property-presence and
board-policy substitutions. The debugger may affect timing. A wrong-board
control returned -12906; a current-board control without the marker returned
-12913. The software control produced six frames matching 691,200 bytes of
the retained CPU reference. A separate CPU fixture calibrated signed `-12913`
and zero at both observation points and refused an incorrect base. All five
video hosts and debuggers terminated under the shared reservation.

The [auditor](../bridge/experiments/video_gva_public_error/audit_gva.py) binds
the signed builds, calibration, same-thread stops, direct caller match, pinned
code, software pixels and run receipts. A copied log with the caller match
changed was rejected even after its receipt hash was updated. [Sanitized
receipt](video-gva-public-error-validation.json). The earlier empty-count
and conditional-path observations are documented [here](VIDEO_GVA_CALLER_FLOW.md);
they were separate cohorts, not a count captured by this witness.

## Reproduction

Requires the exact private lab inputs and profile. Use fresh output paths and
never restart an unresolved debugger or reservation. Capture the private
VideoToolbox region with the lab's `tools/inspect_video_cache.py`, using the
VideoToolbox image, UUID `e7231bea63883d0a95c0a93ce970b96b`, offset `4300698`,
and `--capture-region`. Vendor bytes stay in the private lab.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_public_error
BASE="$R/gva-property-build-20261028-01"
VT="$R/vt-region-new/function-region.private.bin"
C="$R/public-error-cal-new"
CTRL="$R/public-error-control-new"
B="$R/public-error-build-new"
python3 "$E/cpu_calibration.py" --out "$C"
python3 "$E/reserved_cpu.py" --lab "$LAB" --calibration "$C" --out "$CTRL"
python3 "$E/build_gva.py" --lab "$LAB" --base "$BASE" --calibration "$C" --reserved-control "$CTRL" --out "$B"
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/error-cpu-new" --mode cpu --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/error-current-1-new" --mode current --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/error-wrong-new" --mode wrong --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/error-off-new" --mode current --witness off
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/error-current-2-new" --mode current --witness on
python3 "$E/audit_gva.py" --base "$BASE" --build "$B" --calibration "$C" --reserved-control "$CTRL" \
  --context-region "$R/video-gva-interface-create-20261018/function-region.private.bin" --vt-region "$VT" \
  --runs "$R/error-cpu-new" "$R/error-current-1-new" "$R/error-wrong-new" "$R/error-off-new" "$R/error-current-2-new" \
  --out "$R/public-error-audit-new.json"
```
