# Native CAS at a fourth threadgroup atomic slot

An explicitly adapted GTX client now qualifies the native CAS correction for a new shader whose atomic is the fourth element of a four-element threadgroup array. On this pinned compiler profile, the decoded native lock/unlock sequence uses shared address `0xc`. The previous qualified `slot1` source used `0x4`; its native program hash differs from the new one. This is a fixed-offset example, not support for arbitrary or dynamic addresses.

The source-built SDK contains the new `sdk_cas_slot` alongside the existing expected-value, live-noise, permuted-output and unchanged-comparand controls. Diagnosis uses the strengthened [backedge recognizer](CAS_BACKEDGE_SAFETY.md) and the pinned decoder. The new source and its replaced fixture are separately fingerprinted; historical compiled hashes are removed from the derived fixture rather than attributed to the new source.

## GTX evidence

Six signed, serial hosts cover negative inputs, uncommitted preparation, two native baselines and two repaired runs. For **the new slot-3 shader alone**, the repaired runs executed 36 command buffers and 42,660 CAS operations, all matching the independent CPU oracle. The two native baselines show 42,606 incorrect expected-value words in this shader, while the output guard and other checked fields remain subject to the existing verifier. Across all five functions, the repaired runs checked 213,300 operations and 853,200 words, including unchanged-comparand controls. The negative host refuses six inputs before construction and two native code/metadata mismatches.

A separately built module/client from the same source overlay, toolchain and regenerated assets has the same object member and client executable as the tested build. The separate rebuild was not itself rerun on the GPU. The audit checks source substitution, old and new decoded shared offsets, pinned decoder output, current recognizer in all five diagnostics, native/repair results, serialized process records and the independent rebuild. [Sanitized results](cas-slot3-validation.json).

The test is limited to one static shared address, one selected 32-bit weak CAS shape and local sizes 33, 128 and 1024, with two comparison variants and three seeds. It does not establish arbitrary addresses, shaders, general Metal conformance, a system compiler fix, transparent support for ordinary applications or a speedup. No system component or OCLP setting was changed.

## Reproduction on the pinned iMac

Use the local dependencies and reservation protocol in [CAS SDK reproduction](CAS_BACKEDGE_SDK.md). The prior generated cohort is required for the `0x4` comparison; it is not silently recreated or repinned. Use fresh output paths. Each command must succeed and every signed process must be terminal before continuing.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
PREVIOUS="$LAB/results/cas-backedge-sdk-overlay-20261028-01/results/generated"
OV="$LAB/results/cas-slot3-overlay-new"
BUILD="$LAB/results/cas-slot3-client-new"
REBUILD="$LAB/results/cas-slot3-client-rebuild-new"
python3 bridge/tools/cas_slot3_overlay.py --lab-root "$LAB" --out "$OV"
python3 "$OV/tools/prepare_native_cas_sdk.py" --out "$OV/results/generated"
for name in current current-rebuild; do
  python3 "$OV/tools/build_native_cas_sdk_module.py" \
    --assets-from "$OV/results/generated/KeplerNativeCAS/assets" \
    --out "$OV/results/$name" --require-decoder-evidence || exit 1
done
python3 bridge/tools/cas_sdk_qualification.py build --sdk "$OV/results/current/KeplerNativeCAS" --out "$BUILD"
python3 bridge/tools/cas_sdk_qualification.py build --sdk "$OV/results/current-rebuild/KeplerNativeCAS" --out "$REBUILD"
for item in negative:1 prepare:1 native:1 execute:1 native:2 execute:2; do
  mode=${item%:*}; n=${item#*:}
  python3 bridge/tools/cas_sdk_qualification.py run --build "$BUILD" \
    --out "$LAB/results/cas-slot3-$mode-$n" --reservation-root "$LAB" --mode "$mode" || exit 1
done
python3 bridge/tools/audit_cas_slot3.py --generated "$OV/results/generated" \
  --previous-generated "$PREVIOUS" --build "$BUILD" --final-build "$REBUILD" \
  --module-overlay "$OV" --decoder "$LAB/build/envydis-only/envydis/envydis" --runs \
  "$LAB/results/cas-slot3-negative-1" "$LAB/results/cas-slot3-prepare-1" \
  "$LAB/results/cas-slot3-native-1" "$LAB/results/cas-slot3-execute-1" \
  "$LAB/results/cas-slot3-native-2" "$LAB/results/cas-slot3-execute-2" \
  --out "$LAB/results/cas-slot3-audit-new.json"
python3 -m unittest discover -s tests -p '*cas*.py' -v
```

The new original MSL source SHA-256 is `5250623b90ddd3571a15621143cab8e58809cdb579e7533c012fa0ea7a80c994`; the captured native code hash is `f41a7c60ac081d3e77ebfba77dcf5eff3dab70b9129e958689de244c03adfe02`. The audited signer and GPU receipts, captured vendor program and compiled certificates remain in the local lab and are not distributed.
