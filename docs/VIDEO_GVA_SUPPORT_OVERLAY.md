# AppleGVA support-table counterfactual

**Calibration safety:** Do not use this historical observer in calibration mode with arbitrary clients. An extended calibration crashed when an opaque dictionary key was inspected as a Core Foundation object. The newer [property observer](VIDEO_GVA_PROPERTY.md) restricts calibration to an explicitly armed key and checks an opaque-key control. This warning does not change the archived observations.

A pinned AppleGVA initialization path reads the iMac's model and board identifier from the locally installed `System Support` table. In three fresh H.264 hardware-required runs, both lookups returned absent. A separate process-local counterfactual supplies the value of an existing board entry only for the missing iMac board lookup. The lookup succeeds in three repeated runs and AppleGVA's observed logging changes, but **all still return -12913 and zero hardware images**. This is a diagnostic result, not a hardware decoder or driver correction.

## What changed and what was observed

The earlier [board-read witness](VIDEO_GVA_BOARD_OBSERVATION.md) did not establish the actual caller. A new bounded backtrace contains AppleGVA return offsets 152101, 149133, 117072, 232932, 115492 and 264163. The [cache map](video-gva-support-stack-map.json) matches the first three call targets to the 213-byte board reader and its 2,669-byte caller at image offset 148746. The other frame mappings and direct-target limitations are retained in the record. The stack is incomplete by design. Only selected loaded regions are hash-pinned; the remaining mapped frame bodies are cache evidence, not independently verified resident instructions.

At two hash-pinned public `CFDictionaryGetValueIfPresent` callsites in the 2,669-byte region, the observer records original absent results for `iMac11,1` and `Mac-F2268DAE`. On the `patched` route only, when the latter call, exact board key, original absent result, exact image/region pins and complete installed table match all hold, the observer returns a **borrowed existing value from that same dictionary** for `Mac-27ADBB7B4CEE8E61`. The source file and dictionary are not modified. This creates a test-only counterfactual; the donor profile is not asserted to describe the 880M.

| Hardware-required processes | Original board lookup | Returned board lookup | Public create | Images |
| --- | --- | --- | --- | --- |
| Three `current` controls | absent | absent | -12913 | 0 |
| Three `patched` cases | absent | present, scoped substitution | -12913 | 0 |
| Two without the new observer | not observed | not observed | -12913 | 0 |
| Original policy and wrong-board controls | not observed | not observed | -12906 | 0 |

In the first six processes, the existing public-syslog observer records two calls at AppleGVA return offset 146746 that report no plugin, and one renderer-loading error at 148293. Only the three `patched` processes also record messages at 143908 and 144196 concerning an iGPU IOService lookup. The log observer forwards through public `vsyslog`; its original caller return address is not preserved. These messages and the difference in the controlled cases narrow the path but do not identify every provider, prove an absent NVIDIA hardware block, or establish the precise cause of -12913.

The new dependency observer also watches the `IORegistryEntrySearchCFProperty` callsite at AppleGVA return offset 149913, forwarding its real result unchanged and keeping the existing VideoToolbox substitution scoped to its original callsite. No matching AppleGVA event was captured in these six trials. That absence does not prove that no such call happened: the path may not have reached it, or the instrumentation may not have captured it.

The [audit](video-gva-support-overlay-validation.json) checks **13 signed, terminal, nonoverlapping processes**, all frozen inputs, the explicit current accelerator ID, the source transformation, each scoped lookup, the logs and existing controls. A software control's six images match **691,200 CPU-reference bytes**. The [mutation test](video-gva-support-overlay-mutation.json) rejects four altered evidence cases and accepts the unchanged copy. A direct calibration checks the public dictionary and data observer on known inputs; it does not certify every API call or general ABI transparency. Original calibration, unmodified and wrong-policy controls remain available in the local lab.

The experiment uses the previously qualified process-local native transport and VideoToolbox dependency/policy counterfactuals. It adds a separate lookup counterfactual. It does not change the installed driver, macOS frameworks, OCLP or firmware; no vendor code is distributed, no GPU-video execution is proved and no benchmark is claimed. The next useful work is to determine why enumeration produces the reported provider failure and whether a legitimate NVIDIA video provider can supply the missing transport, without treating an unrelated board profile as a fix.

## Reproduction on the exact profile

Use the retained private laboratory prerequisites as in [the previous board experiment](VIDEO_GVA_BOARD_OBSERVATION.md). The current sole `nvAccelerator` ID and driver hash are checked explicitly. The final auditor is intentionally pinned to this ID and capture profile; after a restart or system update, requalify rather than silently changing the evidence. Choose fresh paths, keep the same shared reservation root, and inspect any nonterminal process before retrying.

```sh
EXP=bridge/experiments/video_gva_support_overlay
python3 "$EXP/experiment.py" build --base "$LAB/results/video-factory-resolver-build-20261018-09" --out "$LAB/results/gva-overlay-build-new" --accel-id 4294968416
for mode in calibration inspect cpu; do
  python3 "$EXP/experiment.py" run --build "$LAB/results/gva-overlay-build-new" --out "$LAB/results/gva-overlay-$mode-new" --reservation-root "$LAB" --mode "$mode"
done
for mode in current patched; do
  python3 "$EXP/experiment.py" run --build "$LAB/results/gva-overlay-build-new" --out "$LAB/results/gva-overlay-$mode-1-new" --reservation-root "$LAB" --mode "$mode"
done
for mode in native wrong; do
  python3 "$EXP/experiment.py" run --build "$LAB/results/gva-overlay-build-new" --out "$LAB/results/gva-overlay-$mode-new" --reservation-root "$LAB" --mode "$mode"
done
for n in 1 2; do
  python3 "$EXP/plain.py" --build "$LAB/results/gva-overlay-build-new" --out "$LAB/results/gva-overlay-plain-$n-new" --reservation-root "$LAB" --policy current-board
  if [ "$n" = 1 ]; then for mode in current patched; do python3 "$EXP/experiment.py" run --build "$LAB/results/gva-overlay-build-new" --out "$LAB/results/gva-overlay-$mode-2-new" --reservation-root "$LAB" --mode "$mode"; done; fi
done
for mode in current patched; do python3 "$EXP/experiment.py" run --build "$LAB/results/gva-overlay-build-new" --out "$LAB/results/gva-overlay-$mode-3-new" --reservation-root "$LAB" --mode "$mode"; done
HOSTS=("$LAB/results/gva-overlay-calibration-new" "$LAB/results/gva-overlay-inspect-new" "$LAB/results/gva-overlay-cpu-new" "$LAB/results/gva-overlay-current-1-new" "$LAB/results/gva-overlay-patched-1-new" "$LAB/results/gva-overlay-native-new" "$LAB/results/gva-overlay-wrong-new" "$LAB/results/gva-overlay-plain-1-new" "$LAB/results/gva-overlay-current-2-new" "$LAB/results/gva-overlay-patched-2-new" "$LAB/results/gva-overlay-plain-2-new" "$LAB/results/gva-overlay-current-3-new" "$LAB/results/gva-overlay-patched-3-new")
python3 "$EXP/audit.py" --build "$LAB/results/gva-overlay-build-new" --out "$LAB/results/gva-overlay-audit-new.json" --hosts "${HOSTS[@]}"
python3 "$EXP/mutate.py" --build "$LAB/results/gva-overlay-build-new" --hosts "${HOSTS[@]}"
python3 "$EXP/stack_map.py" --cache "$CACHE" --host "$LAB/results/gva-overlay-current-1-new" --out "$LAB/results/gva-overlay-stack-new.json"
```
