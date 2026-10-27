# Scoped native CAS repair with pipeline reflection

The explicit process-local [standalone CAS bootstrap](STANDALONE_CAS_OPTIONS.md)
now also handles the public options factory when the caller requests both
`MTLPipelineOptionArgumentInfo` and `MTLPipelineOptionBufferTypeInfo` and
provides a reflection output pointer. For four exact certified functions it
calls the existing `KPCertifiedNativeCASFactory`, passing the function created
from the pinned immutable library. The native Metal pipeline factory produces
both the reflection and the certified patched pipeline within the existing
serialized constructor hook. Reflection is not synthesized from a separate
pipeline. A fifth comparand control remains native.

The repair still requires explicit injection into one purpose-built signed
client and exact library, manifest, certificate, device and driver identity.
The caller uses public Metal APIs and imports no KeplerMetal symbols. This is
not an installed-driver correction, transparent support for unrelated apps,
or a general shader repair. Other option combinations and unsupported
functions remain on their existing native paths. If the scoped reflection
constructor or its checks fail, the experimental bootstrap returns no pipeline
and clears the reflection output; that failure branch was not separately
injected in this cohort.

## Qualification

The same signed client, library and 30-dispatch matrix ran twice natively and
twice with the opt-in repair. The two native runs produced **56,808 expected
incorrect words** for the known defective CAS return. The two repaired runs
produced **71,100 CPU-verified CAS operations**, including the unchanged
comparand control. Each host checked guard bytes and used local sizes 33, 128
and 1,024 with two variants for each of five functions. No performance claim
is made.

The returned reflection was present in all four processes. For the three
arguments of each function, the audit compares name, index, type, access,
active state, buffer data type, buffer size and alignment, plus the recorded
pipeline thread limit. These selected values match across all four hosts. It
does **not** compare nested structure members or every reflection property,
and is not general reflection conformance.

Additional same-build hosts verified the earlier zero-options/no-reflection
repair and simple factory, plus a zero-options reflection request that remains
native and reproduces the known defect. Changed-client and changed-certificate controls were refused before user
dispatch. A foreign library stayed native without user dispatch; that control
uses the simple factory. Ten hosts were terminal and nonoverlapping
under the cooperative reservation. The [audit](standalone-cas-reflection-validation.json)
checks the frozen inputs, constructor proofs, numerical outputs and selected
reflection fields; it rejects a modified reflection field and six other offline
mutations. The initial ten-host exploration used an earlier bootstrap build and
is retained separately, not added to these counts. The cooperative reservation
does not exclude WindowServer or unrelated processes.

## Reproduction

Use the exact previously qualified CAS SDK and shader source, the pinned iMac
profile, a shared lab reservation `LAB`, and the current verified GTX registry
ID `RID`. Choose fresh paths. The bootstrap affects only its explicitly
launched signed child. Do not overlap GPU hosts.

```sh
EXP=bridge/experiments/standalone_cas_reflection
python3 "$EXP/experiment.py" build --sdk "$SDK" --shader "$SHADER" --out "$LAB/results/cas-reflection-build-new"
for item in native-reflect:1 optin-reflect:1 native-reflect:2 optin-reflect:2 optin-option:1 optin-reflection:1 optin:1 wrong-library:1 wrong-client:1 wrong-cert:1; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/cas-reflection-build-new" \
    --out "$LAB/results/cas-reflection-$mode-$n" --reservation-root "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/cas-reflection-build-new" \
  --runs "$LAB/results/cas-reflection-native-reflect-1" "$LAB/results/cas-reflection-optin-reflect-1" \
    "$LAB/results/cas-reflection-native-reflect-2" "$LAB/results/cas-reflection-optin-reflect-2" \
    "$LAB/results/cas-reflection-optin-option-1" "$LAB/results/cas-reflection-optin-reflection-1" \
    "$LAB/results/cas-reflection-optin-1" "$LAB/results/cas-reflection-wrong-library-1" \
    "$LAB/results/cas-reflection-wrong-client-1" "$LAB/results/cas-reflection-wrong-cert-1"
python3 "$EXP/mutation_audit.py" --optin "$LAB/results/cas-reflection-optin-reflect-1"
```

The SDK is built and qualified as described in
[CAS SDK regeneration](CAS_SDK_REGENERATED.md). No proprietary Apple or NVIDIA
binary is distributed. Concurrent pipeline construction, other option
combinations, complete reflection, asynchronous and descriptor factories,
hardened apps, performance and system-wide integration remain outside this
qualification.
