# Certified CAS through URL and data Metal library loading

The opt-in, process-local CAS bootstrap now handles the same pinned, certified Metal library when a test client loads it with either `newLibraryWithURL:error:` or `newLibraryWithData:error:`. For the data entry point, the bootstrap maps the input, checks the full bytes against its immutable certified snapshot and constructs the approved library from that snapshot. A different valid library is forwarded to the original Metal factory. Calls made by the internal certified pipeline construction bypass this interception, avoiding reclassification of internal loads as client loads.

The client is purpose-built and imports no KeplerMetal symbols. A and B are two signed builds of the same source, using the URL and data modes respectively; they are not independent third-party applications. The data input in this test is made from a single `NSData` buffer. Segmented dispatch data, arbitrary applications and libraries, concurrent interposition, hardened applications and transparent system-wide operation remain unqualified. As before, a locally supplied policy hash is a snapshot check, not an independent authorization boundary.

## GTX evidence

Thirteen signed processes were run serially under the shared cooperative reservation: seven no-dispatch refusal or pass-through controls, two native baselines and four corrected runs. The data-path baseline reproduces the native defects; its two corrected runs check **213,300 CAS operations across five functions**, including **42,660** from the runtime-indexed shader. The two URL-path corrected runs check the same number independently. Both paths preserve the selected reflection fields and pass their CPU oracles, including guards and the adjacent shared-memory sentinel.

For the dynamic shader, the native baseline in each path produces 21,303 incorrect expected-value words. The test covers source-level indices 0–3, not independent physical address tracing. The data library control passes a different valid library to the native factory with no user dispatch or repair. Controls also cover a changed executable, certificate or policy, unlisted executable, foreign URL library and unsupported descriptor. The audit checks identities, source and asset pins, non-overlapping signed hosts, import proofs and raw output; separate offline mutation controls reject corrupted evidence and a missing data-path witness. [Audit](standalone-data-cas-validation.json) · [General mutations](standalone-data-cas-mutation-validation.json) · [Data witness mutation](standalone-data-cas-path-mutation.json).

An earlier test was terminal but failed its trace check: the internal pipeline factory also used the newly intercepted data method. Its outputs were retained locally and excluded from these figures. After adding the internal-construction bypass, the entire 13-process cohort was rebuilt and repeated. A temporary-copy mutation test initially used an unresolved macOS `/var` path; it was fixed to resolve the path and rerun successfully, without GPU work.

No system driver, framework or OCLP setting is changed. This is neither a general compiler repair nor a performance measurement.

## Reproduction

Use the exact locally qualified `SDK`, `SHADER`, reservation root `LAB` and current device registry ID `RID` described in [the previous client experiment](STANDALONE_DYNAMIC_CAS.md). The builder deliberately pins the same validated SDK assets; a different compiler or driver requires fresh qualification. Use new paths; never submit another host while a previous lease remains unresolved.

```sh
set -e
EXP=bridge/experiments/standalone_data_cas
BUILD="$LAB/results/standalone-data-build-new"
python3 "$EXP/experiment.py" build --sdk "$SDK" --shader "$SHADER" --out "$BUILD"
for item in wrong-data:1 optin-a:1 optin-b:1 native-a:1 native-b:1 optin-a:2 optin-b:2 wrong-client:1 wrong-cert:1 wrong-policy:1 denied-b:1 wrong-library:1 wrong-descriptor:1; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$BUILD" --reservation-root "$LAB" \
    --registry-id "$RID" --mode "$mode" --out "$LAB/results/standalone-data-$mode-$n"
done
python3 "$EXP/audit.py" --build "$BUILD" --runs \
  "$LAB/results/standalone-data-native-a-1" "$LAB/results/standalone-data-native-b-1" \
  "$LAB/results/standalone-data-optin-a-1" "$LAB/results/standalone-data-optin-a-2" \
  "$LAB/results/standalone-data-optin-b-1" "$LAB/results/standalone-data-optin-b-2" \
  "$LAB/results/standalone-data-denied-b-1" "$LAB/results/standalone-data-wrong-policy-1" \
  "$LAB/results/standalone-data-wrong-library-1" "$LAB/results/standalone-data-wrong-data-1" \
  "$LAB/results/standalone-data-wrong-descriptor-1" "$LAB/results/standalone-data-wrong-client-1" \
  "$LAB/results/standalone-data-wrong-cert-1"
python3 "$EXP/mutation_audit.py" --optin "$LAB/results/standalone-data-optin-a-1"
python3 "$EXP/data_mutation_audit.py" --optin-data "$LAB/results/standalone-data-optin-b-1"
```

The cooperative reservation does not exclude unrelated GPU workloads. Proprietary programs, compiled libraries and private captures remain in the laboratory; they are not included in the repository.
