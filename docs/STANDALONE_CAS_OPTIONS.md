# Scoped native CAS repair through the options pipeline factory

The explicit, process-local [standalone CAS bootstrap](STANDALONE_CAS.md) now
also recognizes the public Metal method
`newComputePipelineStateWithFunction:options:reflection:error:` when
`options` is `MTLPipelineOptionNone` and the reflection pointer is null. For
the four already certified functions of the pinned client and library, it
uses the existing certified native NVIDIA program repair. The caller still
uses ordinary Metal APIs and imports no KeplerMetal symbols. This extends the
client-side integration of the existing targeted fix; it does not modify the
installed compiler, driver or system Metal implementation.

The scope is deliberately narrow: the same exact executable, manifest,
certificates, library, device and driver profile must pass the existing gates.
Calls requesting reflection, nonzero options, unregistered functions or other
libraries are forwarded to the original Metal implementation. Reflection is
not synthesized. The no-reflection, zero-option case is the only new repair
path qualified here. Nonzero options and arbitrary applications are not
qualified; callers must not infer transparent or full Metal support.

## GPU evidence

The same signed client and shader library were run on the GTX with the same
30-dispatch matrix per execution. Two native options-factory processes produced
**56,808 expected incorrect words** in the known defective CAS return value.
Two opt-in options-factory processes produced **71,100 CPU-verified CAS
operations**, including the native comparand control; all guards passed. These
are numerical correctness results, not a benchmark. The client uses local sizes
33, 128 and 1,024, two variants and one iteration for five functions per host.

The same archive and client also passed one native and one repaired regression
using the original simple factory. One opted-in options-factory run requested a
reflection pointer: it stayed on the native path, produced the expected native
CAS errors and emitted no repair event. This confirms the tested fallback, not
correctness of the native CAS result. Changed-client and changed-certificate controls were refused before user
dispatch. A foreign library stayed native without user dispatch; that control
uses the simple factory. Nonzero options were not tested.

The ten processes were terminal and nonoverlapping under the cooperative lab
reservation. The [audit](standalone-cas-options-validation.json) rechecks
source and executable hashes, GPU output, constructor proof and process
receipts. It rejects changed output, duplicated dispatch, changed import proof,
wrong factory tag, changed trace and unresolved reservation in offline mutation
controls. The previous initial two-host options trial used an earlier build and
is retained separately, not added to these counts. The reservation does not
exclude WindowServer or other unrelated GPU processes.

## Reproduction

Use the exact previously qualified SDK and shader source, the pinned iMac
profile, a shared lab reservation `LAB`, and the current verified GTX registry
ID `RID`. Choose fresh paths. The bootstrap is explicitly injected into its own
signed child; it has no effect on unrelated processes. Do not overlap GPU hosts.

```sh
EXP=bridge/experiments/standalone_cas_options
python3 "$EXP/experiment.py" build --sdk "$SDK" --shader "$SHADER" --out "$LAB/results/cas-options-build-new"
for item in native-option:1 optin-option:1 optin-reflection:1 native:1 optin:1 native-option:2 optin-option:2 wrong-library:1 wrong-client:1 wrong-cert:1; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/cas-options-build-new" \
    --out "$LAB/results/cas-options-$mode-$n" --reservation-root "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/cas-options-build-new" \
  --runs "$LAB/results/cas-options-native-option-1" "$LAB/results/cas-options-optin-option-1" \
    "$LAB/results/cas-options-optin-reflection-1" "$LAB/results/cas-options-native-1" \
    "$LAB/results/cas-options-optin-1" "$LAB/results/cas-options-native-option-2" \
    "$LAB/results/cas-options-optin-option-2" "$LAB/results/cas-options-wrong-library-1" \
    "$LAB/results/cas-options-wrong-client-1" "$LAB/results/cas-options-wrong-cert-1"
python3 "$EXP/mutation_audit.py" --optin "$LAB/results/cas-options-optin-option-1"
```

The SDK is separately built and qualified as described in
[CAS SDK regeneration](CAS_SDK_REGENERATED.md). No proprietary Apple or NVIDIA
binary is included. Concurrent pipeline construction, nonzero option semantics,
reflection on a repaired pipeline, descriptor and asynchronous factories,
hardened apps, performance, and system-wide integration remain outside the
validated scope.
