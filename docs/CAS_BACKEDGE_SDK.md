# CAS SDK qualification after backedge refusal

The single-overlay source recipe from [the earlier SDK milestone](CAS_SDK_REGENERATED.md) has now been exercised end to end with the [post-redirect backedge check](CAS_BACKEDGE_SAFETY.md). The exact updated recognizer was copied into all five diagnoses; the independent auditor checks its hash and re-evaluates each candidate's structural diagnosis. Four candidate certificates were generated and the original-comparand control was rejected as a repair candidate.

Six signed client processes ran serially on the GTX 880M: one negative, one preparation without user GPU dispatch, two native controls and two repaired executions. The repaired runs used **180 command buffers and 213,300 CAS operations including unchanged-comparand controls**; all 853,200 output words matched the CPU oracle. The two native controls reproduced 170,424 wrong expected-value words in the affected cases. The negative client refused six inputs before the constructor and two at native code/metadata checks. Twenty-one signed preparation processes were also audited as terminal and nonoverlapping; capture and compilation are not GPU execution proof.

A separately built module and client from the same overlay, toolchain and regenerated assets were compared with the GPU-tested build: the object member and client executable matched byte-for-byte. The rebuilt archive container's hash differed; the second client was not run on the GPU. This is a reproducibility comparison, not independent GPU qualification.

The modified backedge program itself remains a deliberately mismatched synthetic AIR/SASS pair and was never dispatched. This cohort tests the same four bounded shader shapes after diagnosis with the stronger recognizer; it does not qualify arbitrary shaders, revoke existing certificates, fix the installed compiler or prove complete control-flow safety. Regenerate and individually qualify policies for other shaders. No performance claim, driver replacement or system-wide application support is implied.

## Reproduce on the pinned iMac

Obtain the existing lab dependencies as described in [Dependencies](DEPENDENCIES.md). Use fresh paths; the shared reservation coordinates all signed preparation and client processes. Inspect failures and resolve any nonterminal child before continuing. The source recipe is tied to the exact target profile and the pinned local decoder.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
OVERLAY="$LAB/results/cas-sdk-backedge-overlay-new"
BUILD="$LAB/results/cas-sdk-backedge-client-new"
REBUILD="$LAB/results/cas-sdk-backedge-client-rebuild-new"
python3 bridge/tools/cas_sdk_source_overlay.py --lab-root "$LAB" --out "$OVERLAY"
python3 "$OVERLAY/tools/prepare_native_cas_sdk.py" --out "$OVERLAY/results/generated"
for name in current current-rebuild; do
  python3 "$OVERLAY/tools/build_native_cas_sdk_module.py" \
    --assets-from "$OVERLAY/results/generated/KeplerNativeCAS/assets" \
    --out "$OVERLAY/results/$name" --require-decoder-evidence || break
done
python3 bridge/tools/cas_sdk_qualification.py build --sdk "$OVERLAY/results/current/KeplerNativeCAS" --out "$BUILD"
python3 bridge/tools/cas_sdk_qualification.py build --sdk "$OVERLAY/results/current-rebuild/KeplerNativeCAS" --out "$REBUILD"
for item in negative:1 prepare:1 native:1 execute:1 native:2 execute:2; do
  mode=${item%:*}; n=${item#*:}
  python3 bridge/tools/cas_sdk_qualification.py run --build "$BUILD" \
    --out "$LAB/results/cas-sdk-backedge-$mode-$n" --reservation-root "$LAB" --mode "$mode" || break
done
python3 bridge/tools/audit_cas_backedge_sdk.py --generated "$OVERLAY/results/generated" \
  --build "$BUILD" --final-build "$REBUILD" --module-overlay "$OVERLAY" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --runs \
  "$LAB/results/cas-sdk-backedge-negative-1" "$LAB/results/cas-sdk-backedge-prepare-1" \
  "$LAB/results/cas-sdk-backedge-native-1" "$LAB/results/cas-sdk-backedge-execute-1" \
  "$LAB/results/cas-sdk-backedge-native-2" "$LAB/results/cas-sdk-backedge-execute-2" \
  --out "$LAB/results/cas-sdk-backedge-audit-new.json"
python3 -m unittest discover -s tests -p '*cas*.py' -v
```

[Sanitized validation record](cas-backedge-sdk-validation.json). The 2026-10-28 cohort used recognizer SHA-256 `46116c7d4c9143f46cfc4ee62cf589fe3cbd9cfa9a371388377259a342446352`, GPU client `e30f92877728de9e6171a28dcf74a0c74bb74a022334a3a959e49b52ca00fd05`, and rebuilt object `b45f93488ae92b0fb321589c877d95fe3c19ed517e86476c490beabfe6b36a7c`. Full binaries, certificates, captured programs and private source fixtures remain in the local lab. No system component or OCLP setting was modified.
