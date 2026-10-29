# AppleGVA handles the empty candidate list

In two instrumented H.264 requests, a breakpoint immediately after the
AppleGVA dispatch call observed **result `1` and count `0`**. A second
breakpoint on the same thread then reached the caller's conditional exit path;
the breakpoint at the alternative path had zero hits in each process. Both
requests ultimately returned VideoToolbox status **-12913**, with no images.

The pinned caller compares both the result and count, combines the conditions,
and takes this path if the result is nonzero or the count is zero. The
alternative path includes a later indirect call through offset `0x100`; its
breakpoint being unhit covers these observed executions only, not every call
that might occur elsewhere. This extends the [previous witness](VIDEO_GVA_DISPATCH_RESULT.md),
which stopped before the dispatch epilogue but did not observe its caller.
It still does not establish the meaning of the internal value `1`, the exact
mapping to `-12913`, every provider invocation, or hardware decoding.

The tested requests retain process-local synthetic property and board-policy
substitutions. The debugger can change timing. One wrong-board control returned
-12906; one current-board control without the witness returned -12913. A
software control produced six frames matching 691,200 CPU-reference bytes.
An original CPU fixture calibrated both the conditional path and the
alternative path, with bad-base and unreadable-pointer controls. The shared
reservation was used and all five video hosts and debuggers terminated.

The [audit](../bridge/experiments/video_gva_caller_flow/audit_gva.py) checks the
live-pinned caller and dispatch regions, instruction sequence, calibration,
signed build, same-thread observations, run receipts, software frames and
system-file profile. A copied run with its branch observation changed was
rejected even after its log hash was updated. [Sanitized receipt](video-gva-caller-flow-validation.json).
No proprietary component is distributed or modified.

## Reproduction

Requires the pinned private lab inputs. Use fresh output paths and do not
restart while a debugger or reservation is unresolved.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_caller_flow
BASE="$R/gva-property-build-20261028-01"
C="$R/caller-cal-new"
CTRL="$R/caller-control-new"
B="$R/caller-build-new"
python3 "$E/cpu_calibration.py" --out "$C"
python3 "$E/reserved_cpu.py" --lab "$LAB" --calibration "$C" --out "$CTRL"
python3 "$E/build_gva.py" --lab "$LAB" --base "$BASE" --calibration "$C" --reserved-control "$CTRL" --out "$B"
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/caller-cpu-new" --mode cpu --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/caller-current-1-new" --mode current --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/caller-wrong-new" --mode wrong --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/caller-off-new" --mode current --witness off
python3 "$E/run_gva.py" --lab "$LAB" --base "$BASE" --build "$B" --out "$R/caller-current-2-new" --mode current --witness on
python3 "$E/audit_gva.py" --base "$BASE" --build "$B" --calibration "$C" --reserved-control "$CTRL" \
  --dispatch-region "$R/video-gva-provider-session-20261018/function-region.private.bin" \
  --enumerator-region "$R/gva-post-constructor-20261029-01/function-region.private.bin" \
  --context-region "$R/video-gva-interface-create-20261018/function-region.private.bin" \
  --runs "$R/caller-cpu-new" "$R/caller-current-1-new" "$R/caller-wrong-new" "$R/caller-off-new" "$R/caller-current-2-new" \
  --out "$R/caller-audit-new.json"
```

The next boundary is the exit path's return and its connection to
VideoToolbox, while separately investigating a compatible NVIDIA provider.
