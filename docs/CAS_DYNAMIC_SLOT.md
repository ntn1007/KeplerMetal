# Native CAS with a runtime-selected threadgroup atomic

An explicitly adapted client qualifies one bounded runtime-indexed atomic CAS shader on the GTX 880M. The source chooses `(seed + group) & 3` in a four-element threadgroup array. One neighboring element is initialized as a sentinel and checked in every output; the chosen input combinations cover source-level indices 0, 1, 2 and 3. This is evidence for this test, not independent physical-address tracing or support for arbitrary dynamic shaders.

On the pinned compiler profile the decoded NVIDIA lock/unlock sequence addresses shared memory through `$r2`; the preceding live-noise fixture used `0x0`. The recognizer now permits a register-indexed shared operand only if the same operand is used for the unlock and the address register is not overwritten by the matched lock loop. The existing control-flow and pinned-decoder checks remain in force. These structural conditions do not establish address bounds or full shader semantics: every new shader still needs explicit qualification, and old policies must be regenerated with the updated recognizer.

## GTX evidence

Six serial signed hosts provide negative-input and preparation checks, two native baselines, and two repaired executions. For this new shader alone the repaired runs executed 36 command buffers and **42,660 CAS operations**, all matching the CPU oracle, including the output incorporating the neighboring sentinel. The two native baselines contain **42,606 incorrect expected-value words**. Across all five functions the repaired runs verified 213,300 CAS operations and 853,200 words. The negative host refuses six inputs before construction and two native code/metadata mismatches.

An independent rebuild from the same overlay and regenerated assets produced the same module object and client executable as the GPU-tested build; the rebuild itself was not rerun on the GPU. The audit verifies source provenance, the pinned decoder, input combinations, numerical receipts and rebuild identity. [Sanitized results](cas-dynamic-validation.json).

The test covers one 32-bit weak-CAS shader, local sizes 33, 128 and 1024, three groups, two comparison variants and three seeds. It checks only one neighboring sentinel per group. Other attempted dynamic shader shapes remain rejected by the conservative recognizer. These results do not establish general Metal conformance, a system compiler or driver fix, transparent support for ordinary applications, or a performance gain. No system or OCLP component was changed.

## Reproduction on the pinned iMac

Use the local dependencies and reservation protocol in [CAS SDK reproduction](CAS_BACKEDGE_SDK.md). The previous generated cohort is required for the baseline comparison. Use fresh output paths and stop if any command fails; each signed process must finish before proceeding.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
PREVIOUS="$LAB/results/cas-backedge-sdk-overlay-20261028-01/results/generated"
OV="$LAB/results/cas-dynamic-overlay-new"
BUILD="$LAB/results/cas-dynamic-client-new"
REBUILD="$LAB/results/cas-dynamic-client-rebuild-new"
python3 bridge/tools/cas_dynamic_overlay.py --lab-root "$LAB" --out "$OV"
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
    --out "$LAB/results/cas-dynamic-$mode-$n" --reservation-root "$LAB" --mode "$mode" || exit 1
done
python3 bridge/tools/audit_cas_dynamic.py --generated "$OV/results/generated" \
  --previous-generated "$PREVIOUS" --build "$BUILD" --final-build "$REBUILD" \
  --module-overlay "$OV" --decoder "$LAB/build/envydis-only/envydis/envydis" --runs \
  "$LAB/results/cas-dynamic-negative-1" "$LAB/results/cas-dynamic-prepare-1" \
  "$LAB/results/cas-dynamic-native-1" "$LAB/results/cas-dynamic-execute-1" \
  "$LAB/results/cas-dynamic-native-2" "$LAB/results/cas-dynamic-execute-2" \
  --out "$LAB/results/cas-dynamic-audit-new.json"
python3 -m unittest discover -s tests -p '*cas*.py' -v
```

The shader source SHA-256 is `e140b506aa68b1cace774b8771350ffd9bbd3e9888afd27a71c62577f025a7ad`; the captured NVIDIA code SHA-256 is `7640c32a4ea4a078dd4e3bf149a15f1fef77e4e22a56018f3f5ed6fa2c6f541c`. Vendor programs and signed executable captures remain in the local lab and are not distributed.
