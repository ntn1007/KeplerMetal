# AppleGVA NVIDIA property observation

The scoped H.264 investigation now records three public `IORegistryEntryCreateCFProperty` results returned to pinned AppleGVA callsites. Each of nine fresh own-process hardware requests, across three `current`, three donor `patched` and three donor `no-offline` conditions, queries the same `nvAccelerator` registry entry **4294968416**. The observed results are:

| Key | Returned value |
| --- | --- |
| `IODVDBundleName` | `GeForceVADriver` |
| `IOVARendererID` | number `17039368` |
| `IOGVACodec` | absent (null) |

These are actual API returns to the instrumented process under the existing local VideoToolbox dependency and board-policy counterfactuals, not a claim of hardware decoding. A separate scoped board lookup may also substitute an existing donor profile in the patched modes. The read of a driver bundle name alone does not prove the bundle loaded, a provider was instantiated, or the video engine executed work. Each of those nine requests and one comparison without this observer returned **-12913 and zero images**. No broad diagnosis of the decoder failure follows from the absent property alone.

The [static branch audit](video-gva-property-branch.json) checks the current cache and pinned AppleGVA function capture, then maps the observed property call at image offset 150807 and return at 150812. In that exact capture, a null return takes the conditional branch to offset 150858, skipping the flag write at 150821 and string conversion at 150845. This is a static inference from the observed return and pinned instructions, not a program-counter trace or proof of the later node state. The actual codec property semantics, provider availability and downstream failure are still open.

The [cohort audit](video-gva-property-validation.json) checks **14 signed terminal nonoverlapping processes**, including the nine instrumented requests, an observer-free comparison, a software control, and two calibrations. Six software output images match 691,200 bytes of an independent CPU reference. The [mutation checks](video-gva-property-mutation.json) accept an unchanged copy and reject an altered property record, software frame, policy and lease. These checks do not prove hardware video execution. The observer's selected loaded code regions, driver and local accelerator ID are pinned; these results are not portable to a changed profile without requalification. No installed driver, OCLP, firmware or system framework was modified and no performance gain is claimed.

## Calibration safety

An intermediate **own-process calibration** crashed with `SIGSEGV` while initializing Metal. The local crash report records `objc_msgSend` immediately above `observeLookup`; the intermediate observer could inspect an opaque Core Foundation dictionary key as if it were a CF object. The crash does not establish a kernel or driver defect. The final calibration restricts dictionary inspection to an explicitly armed known key; a separate legal dictionary with opaque key callbacks passed and returned its original value. The prior intermediate crash and failed intermediate calibrations are excluded from the 14-process cohort. This narrowly tested change is not a guarantee for arbitrary processes; the interposer remains a lab instrument.

## Reproduction on the pinned profile

The retained private prerequisites, including the already qualified factory host, AppleGVA capture and fixture, are required; see [dependencies](DEPENDENCIES.md) and [the preceding experiment](VIDEO_GVA_OFFLINE_FLAG.md). The source does not redistribute vendor binaries. Set `LAB` to the private `nvidia-880m-lab/bridge` directory. The local GPU registry ID can change after restart: the auditor deliberately refuses a different ID. Use fresh output paths, the shared reservation, and confirm terminal state before retrying.

```sh
EXP=bridge/experiments/video_gva_property_observer
R="$LAB/results"
B="$R/gva-property-build-new"
python3 "$EXP/experiment.py" build --base "$R/video-factory-resolver-build-20261018-09" --out "$B" --accel-id 4294968416
for mode in calibration inspect cpu; do
  python3 "$EXP/experiment.py" run --build "$B" --out "$R/gva-property-$mode-new" --reservation-root "$LAB" --mode "$mode"
done
for mode in current patched no-offline; do
  python3 "$EXP/experiment.py" run --build "$B" --out "$R/gva-property-$mode-1-new" --reservation-root "$LAB" --mode "$mode"
done
python3 "$EXP/plain.py" --build "$B" --out "$R/gva-property-plain-new" --reservation-root "$LAB" --policy current-board
for mode in current patched no-offline; do
  python3 "$EXP/experiment.py" run --build "$B" --out "$R/gva-property-$mode-2-new" --reservation-root "$LAB" --mode "$mode"
done
for mode in no-offline patched current; do
  python3 "$EXP/experiment.py" run --build "$B" --out "$R/gva-property-$mode-3-new" --reservation-root "$LAB" --mode "$mode"
done
python3 "$EXP/opaque_experiment.py" --build "$B" --out "$R/gva-property-opaque-new" --reservation-root "$LAB"
HOSTS=("$R/gva-property-calibration-new" "$R/gva-property-inspect-new" "$R/gva-property-cpu-new" "$R/gva-property-current-1-new" "$R/gva-property-patched-1-new" "$R/gva-property-no-offline-1-new" "$R/gva-property-plain-new" "$R/gva-property-current-2-new" "$R/gva-property-patched-2-new" "$R/gva-property-no-offline-2-new" "$R/gva-property-no-offline-3-new" "$R/gva-property-patched-3-new" "$R/gva-property-current-3-new" "$R/gva-property-opaque-new")
python3 "$EXP/audit.py" --build "$B" --hosts "${HOSTS[@]}" --out "$R/gva-property-audit-new.json"
python3 "$EXP/mutate.py" --build "$B" --hosts "${HOSTS[@]}"
python3 -m unittest discover -s tests -p 'test_video_gva*.py' -v
```

The separate `branch_audit.py` requires the exact private function capture, mapped stub metadata and shared cache used by the static record. It is pinned to their hashes; rerun only with those verified prerequisites and a fresh output. Future work should identify the legitimate provider and codec-property contract before considering a scoped intervention. Never fabricate a property as proof of hardware support.
