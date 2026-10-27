# One scoped CAS bootstrap for mixed Metal pipeline factories

A single opt-in process-local bootstrap now combines the previously separate
[function/options/reflection](STANDALONE_CAS_REFLECTION.md) and
[default descriptor](DESCRIPTOR_CAS.md) experiments. In the same purpose-built
client and process, four exact certified functions use four public Metal
pipeline factories: the simple function factory; function with zero options;
function with argument and buffer-type reflection; and a default compute
descriptor. A fifth comparand control stays native. The client imports no
KeplerMetal symbols; explicit injection enables the experiment.

The bootstrap retains all existing exact executable, library, manifest,
certificate, device and driver checks. The descriptor path also checks its
bounded default properties and compares pipeline thread limit, execution width
and static threadgroup memory against native descriptor creation. A
nondefault descriptor and foreign library are forwarded to native Metal; a
changed client or certificate is refused. This is not a driver installation,
transparent support for arbitrary apps, or a general CAS fix. Each factory
was exercised with one corresponding certified candidate here, not all
combinations of factory and shader.

## GTX qualification

Two native and two opt-in hosts used the same client, library and 30-dispatch
matrix. The native hosts produced **56,808 expected incorrect words** in the
four defective CAS results. The opt-in hosts produced **71,100 correct
CPU-verified CAS operations**, including the unchanged comparand control.
Local sizes 33, 128 and 1,024 and two variants were tested; all output guards
passed. A separate output checks the selected reflection fields for three
arguments of the reflection-path shader against native; nested structure
members and the full reflection contract are not compared.

Four other signed hosts checked changed client, changed certificate, foreign
library and nondefault descriptor, without user shader dispatch. The foreign
library and descriptor controls stayed native rather than receiving the
repair. Eight processes were terminal and nonoverlapping under the shared lab
reservation. The [audit](standalone-cas-unified-validation.json) rechecks
inputs, each factory's constructor proof, CPU output and selected reflection;
it rejects an altered reflection field and six other offline mutations. No
performance benchmark was run. The reservation does not exclude WindowServer
or unrelated processes.

## Reproduction

Use the exact qualified CAS `SDK`, original `SHADER`, shared lab reservation
`LAB`, and the current verified GTX registry ID `RID`. Choose fresh paths and
stop after an unresolved or failed process. No proprietary vendor binary is
included in this repository.

```sh
EXP=bridge/experiments/standalone_cas_unified
python3 "$EXP/experiment.py" build --sdk "$SDK" --shader "$SHADER" --out "$LAB/results/cas-unified-build-new"
for item in native:1 optin:1 native:2 optin:2 wrong-library:1 wrong-descriptor:1 wrong-client:1 wrong-cert:1; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/cas-unified-build-new" \
    --out "$LAB/results/cas-unified-$mode-$n" --reservation-root "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/cas-unified-build-new" \
  --runs "$LAB/results/cas-unified-native-1" "$LAB/results/cas-unified-optin-1" \
    "$LAB/results/cas-unified-native-2" "$LAB/results/cas-unified-optin-2" \
    "$LAB/results/cas-unified-wrong-library-1" "$LAB/results/cas-unified-wrong-descriptor-1" \
    "$LAB/results/cas-unified-wrong-client-1" "$LAB/results/cas-unified-wrong-cert-1"
python3 "$EXP/mutation_audit.py" --optin "$LAB/results/cas-unified-optin-1"
```

The SDK is qualified as described in [CAS SDK regeneration](CAS_SDK_REGENERATED.md).
Concurrent pipeline construction, descriptor reflection, other option
combinations, full reflection, asynchronous factories, hardened applications,
performance and system-wide integration remain open. The earlier standalone
experiments remain preserved as independent evidence; this new bootstrap does
not alter macOS, OCLP or an installed driver.
