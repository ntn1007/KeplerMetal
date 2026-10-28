# AppleGVA offline-renderer flag: controlled comparison

**Calibration safety:** Do not use this historical observer in calibration mode with arbitrary clients. An extended calibration crashed when an opaque dictionary key was inspected as a Core Foundation object. The newer [property observer](VIDEO_GVA_PROPERTY.md) restricts calibration to an explicitly armed key and checks an opaque-key control. This warning does not change the archived observations.

The previous [support-table experiment](VIDEO_GVA_SUPPORT_OVERLAY.md) used a donor entry that contains `forceOfflineRenderer=true`. In this process-local follow-up, the same donor dictionary is used in both groups. In one group, an owned copy removes exactly that key; the code checks the key was originally true and verifies that adding it back produces a `CFEqual` dictionary. The original dictionary and system property list are not modified. Both groups retain the earlier narrowly scoped, hardware-required test conditions.

Three runs with the original donor produce two iGPU-related log entries at AppleGVA return offsets 143908 and 144196. Three runs with only that key removed produce neither entry. All six still report two provider-absence logs at offset 146746, public decoder status **-12913**, and **zero hardware images**. This supports a causal role for the donor flag in the observed log difference under these conditions. It does not establish an NVIDIA provider, successful decoding, or a general fix. The public-syslog observer forwards through `vsyslog` and does not preserve the original caller return address; these observations are not performance measurements.

## Bounded iterator observation

A separate interposer forwards `IORegistryCreateIterator` and `IOIteratorNext` with their original results, observing only three pinned return offsets in the 2,669-byte AppleGVA region. A known public IOKit calibration successfully creates and advances an iterator. No matching iterator event is captured in any of the six comparison processes, and no matching `IOGVACodec` property-query event is captured by the preceding observer. The calibration does **not** prove that calls from AppleGVA are interposed, so these zero counts do not establish that enumeration was not reached or that a GPU was absent. No result, iterator or IOKit object is replaced or released by these observers.

The [audit](video-gva-offline-flag-validation.json) rechecks **13 signed, terminal, nonoverlapping processes**, the pinned current driver and registry ID, frozen sources and binaries, the actual lookup and profile evidence, log offsets, controls and frame data. Six software images match **691,200 bytes** of the independent CPU reference. The [offline mutations](video-gva-offline-flag-mutation.json) refuse four altered evidence cases and retain the unchanged control. A prior exploratory build is excluded from these totals. No hardware-video execution or performance gain is claimed, and no installed driver, framework, OCLP or firmware was changed.

The next step is to locate the provider/transport failure through observed calls that are demonstrably reached; the lack of iterator events is not itself a diagnosis. A legitimate NVIDIA provider and its resource and submission contract remain unqualified.

## Reproduction on the exact profile

The build reuses the pinned private laboratory host described in [the previous experiment](VIDEO_GVA_SUPPORT_OVERLAY.md). Vendor inputs remain local and are not redistributed. The accelerator ID and GeForce hash are explicitly checked; requalify if they change. Use fresh paths, one shared lab reservation and do not retry a nonterminal process.

```sh
EXP=bridge/experiments/video_gva_offline_flag
python3 "$EXP/experiment.py" build --base "$LAB/results/video-factory-resolver-build-20261018-09" --out "$LAB/results/gva-offline-build-new" --accel-id 4294968416
for mode in calibration inspect cpu current native wrong; do
  python3 "$EXP/experiment.py" run --build "$LAB/results/gva-offline-build-new" --out "$LAB/results/gva-offline-$mode-0-new" --reservation-root "$LAB" --mode "$mode"
done
python3 "$EXP/plain.py" --build "$LAB/results/gva-offline-build-new" --out "$LAB/results/gva-offline-plain-0-new" --reservation-root "$LAB" --policy current-board
for item in patched:1 no-offline:1 no-offline:2 patched:2 patched:3 no-offline:3; do
  mode="${item%:*}"; n="${item#*:}"
  python3 "$EXP/experiment.py" run --build "$LAB/results/gva-offline-build-new" --out "$LAB/results/gva-offline-$mode-$n-new" --reservation-root "$LAB" --mode "$mode"
done
HOSTS=("$LAB/results/gva-offline-calibration-0-new" "$LAB/results/gva-offline-inspect-0-new" "$LAB/results/gva-offline-cpu-0-new" "$LAB/results/gva-offline-current-0-new" "$LAB/results/gva-offline-native-0-new" "$LAB/results/gva-offline-wrong-0-new" "$LAB/results/gva-offline-plain-0-new" "$LAB/results/gva-offline-patched-1-new" "$LAB/results/gva-offline-no-offline-1-new" "$LAB/results/gva-offline-no-offline-2-new" "$LAB/results/gva-offline-patched-2-new" "$LAB/results/gva-offline-patched-3-new" "$LAB/results/gva-offline-no-offline-3-new")
python3 "$EXP/audit.py" --build "$LAB/results/gva-offline-build-new" --out "$LAB/results/gva-offline-audit-new.json" --hosts "${HOSTS[@]}"
python3 "$EXP/mutate.py" --build "$LAB/results/gva-offline-build-new" --hosts "${HOSTS[@]}"
```
