# Runtime-indexed native CAS in a public Metal client

A purpose-built client using Metal and Foundation, with no KeplerMetal symbols, executes the [qualified runtime-indexed CAS shader](CAS_DYNAMIC_SLOT.md) with an explicitly loaded, process-local bootstrap. The bootstrap recognizes an exact certified library and allowed client, intercepts selected pipeline constructions and uses the existing native CAS repair. The client source is built twice with distinct signed hashes; these are two builds of the same test program, not independent third-party applications.

This extends the earlier dynamic-shader qualification to the public-Metal client path. It does not install a driver, alter a system framework, make injection transparent, or establish support for arbitrary applications, libraries, concurrent interposition or hardened applications. The policy hash is supplied by the launcher; it checks a snapshot and is not an independent authorization boundary. The user must trust and keep the inputs immutable.

## GTX 880M evidence

Twelve signed processes ran serially under the common cooperative GPU reservation. Six were no-dispatch refusal or pass-through controls: changed client, certificate or policy; unlisted client; different library; and nondefault descriptor. Two native clients reproduced 170,424 incorrect expected-value words across the four defective shaders; the remaining CAS fields and unchanged-comparand control matched their oracle.

Four corrected runs checked **426,600 CAS operations** across all five functions. For the new dynamic shader alone, these runs checked **85,320 CAS operations** over 72 command buffers. Two native runs of that shader had **42,606 incorrect expected-value words**. Three seeds and three groups cover source-level indices 0–3; one adjacent shared element is checked as a sentinel. These inputs do not independently trace physical shared-memory addresses. The oracle checks each output word and guards, and selected Metal reflection fields match in all six GPU hosts.

The auditor rechecks the signed processes, serialized reservations, binaries and input hashes, import records and raw outputs. Eight offline mutations are rejected; an unchanged copy passes. [Audit](standalone-dynamic-cas-validation.json) · [Mutation controls](standalone-dynamic-cas-mutation-validation.json). The same SDK archive and shader were previously qualified separately; the new client processes are the GPU evidence for this integration, not the earlier SDK runs. No performance comparison was made.

## Reproduction

This experiment deliberately pins the exact locally qualified SDK archive, client manifest, library, certificates and combined shader. Regenerate or obtain the SDK using [the dynamic shader procedure](CAS_DYNAMIC_SLOT.md), then verify its audit before proceeding. A different compiler output or driver needs a new qualification; do not change these pins to force a pass. `SDK` points to `OV/results/current/KeplerNativeCAS` and `SHADER` to `OV/results/generated/KeplerNativeCAS/examples/cas_client.metal` from that procedure. `LAB` is the shared laboratory reservation root and `RID` is the current GTX registry ID. Use new output paths and stop if any process or lease is unresolved.

```sh
set -e
EXP=bridge/experiments/standalone_dynamic_cas
BUILD="$LAB/results/standalone-dynamic-build-new"
python3 "$EXP/experiment.py" build --sdk "$SDK" --shader "$SHADER" --out "$BUILD"
for item in wrong-client:1 wrong-cert:1 wrong-policy:1 denied-b:1 wrong-library:1 wrong-descriptor:1 native-a:1 optin-a:1 native-b:1 optin-b:1 optin-a:2 optin-b:2; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$BUILD" --reservation-root "$LAB" \
    --registry-id "$RID" --mode "$mode" --out "$LAB/results/standalone-dynamic-$mode-$n"
done
python3 "$EXP/audit.py" --build "$BUILD" --runs \
  "$LAB/results/standalone-dynamic-native-a-1" "$LAB/results/standalone-dynamic-native-b-1" \
  "$LAB/results/standalone-dynamic-optin-a-1" "$LAB/results/standalone-dynamic-optin-a-2" \
  "$LAB/results/standalone-dynamic-optin-b-1" "$LAB/results/standalone-dynamic-optin-b-2" \
  "$LAB/results/standalone-dynamic-denied-b-1" "$LAB/results/standalone-dynamic-wrong-policy-1" \
  "$LAB/results/standalone-dynamic-wrong-library-1" "$LAB/results/standalone-dynamic-wrong-descriptor-1" \
  "$LAB/results/standalone-dynamic-wrong-client-1" "$LAB/results/standalone-dynamic-wrong-cert-1"
python3 "$EXP/mutation_audit.py" --optin "$LAB/results/standalone-dynamic-optin-a-1"
```

The cooperative lease coordinates participating test runners, not WindowServer or unrelated workloads. Raw native programs, compiled libraries, signed executables, private captures and any Apple/NVIDIA proprietary binaries remain local and are not published.
