# Process-local native CAS repair for a public-Metal client

This experiment runs one **purpose-built executable** that uses ordinary Metal
and Foundation APIs and imports no KeplerMetal symbols. The executable asks
Metal to load a library, find five functions and build their compute pipelines.
An explicit launcher may inject a separately built bootstrap into that process.
The exact same signed client is used with and without that bootstrap.

The bootstrap admits one exact client hash, one previously qualified library
hash, the exact manifest and certificate hashes, and a GTX 880M identified by
its PCI vendor/device IDs. It adapts only the selected device and library
objects in the child process. Four matching compute-pipeline creations use the
existing `KPCreateCertifiedNativeCASPipeline` path; the fifth, an intentional
original-comparand semantic control, remains native. A thread-local recursion
guard lets the internal certified pipeline construction call the native Metal
factory. A different library is passed through to native Metal; a changed client
or certificate is refused before a user dispatch.

This is an opt-in, process-local demonstration, not a driver installation or a
general repair for existing applications. The client was created for this test;
it is not an independently supplied application. Only the tested library and
simple `newComputePipelineStateWithFunction:error:` path are recognized.
Descriptor/async pipeline factories, multiple libraries, arbitrary code,
concurrent application pipeline construction, hardened applications and
system-wide integration are not qualified. The bootstrap uses process-local
Objective-C subclasses and the existing temporary native constructor hook;
the application must serialize other interposition in that process. No claim is
made about resident instruction readback or a performance improvement.

## GTX qualification

Seven fresh signed hosts were run serially with the common laboratory lease:
two native baselines, two opt-in executions and three no-dispatch controls. In
the baselines, the four defective cases produced **170,424 wrong expected-value
words** over 180 command buffers, while their CAS success/final/index fields and
the original-comparand control passed. With the bootstrap, 180 command buffers
produced **213,300 correct CAS operations**, including the semantic controls;
an independent CPU oracle checked every output and guard. This compares the
same executable and same library, not performance.

The controls confirm that a changed executable and a changed certificate are
refused before user dispatch, and that a different valid library is not patched.
The bootstrap's four proofs identify the certificate, native code and metadata
checks and confirm restoration of the temporary constructor hook. The proof
concerns constructor payloads; numerical GPU output supplies the separate
execution check. A CPU-only mutation audit confirms that altered output,
duplicated dispatch metadata, changed proof, changed trace or an unresolved
reservation are refused. The GPU lease is cooperative and does not exclude
WindowServer or unrelated applications.

The first cohort used an earlier verifier and remains local. The final build
uses the complete 90-case matrix and checks the individual certificate and
constructor evidence. [Machine-readable audit](standalone-cas-validation.json) ·
[Oracle mutation controls](standalone-cas-mutation-validation.json) ·
[Regenerated SDK and its qualification](CAS_SDK_REGENERATED.md).

## Reproduction

`SDK` is the locally rebuilt, separately qualified CAS SDK from the preceding
experiment; `SHADER` is that preparation's `cas_client.metal` source; `LAB` is
the shared laboratory reservation root, and `RID` is the GTX registry ID for
the current boot. Use the exact qualified system profile and fresh output paths.
The builder verifies the SDK object and certificate pins and copies local
artifacts only into the isolated output. No Apple/NVIDIA binary is distributed.

```sh
python3 bridge/experiments/standalone_cas/experiment.py build \
  --sdk "$SDK" --shader "$SHADER" --out "$LAB/results/standalone-cas-build-new"
for mode in wrong-client wrong-cert wrong-library native optin; do
  python3 bridge/experiments/standalone_cas/experiment.py run \
    --build "$LAB/results/standalone-cas-build-new" --out "$LAB/results/standalone-cas-$mode-new" \
    --reservation-root "$LAB" --registry-id "$RID" --mode "$mode" || break
done
for mode in native optin; do
  python3 bridge/experiments/standalone_cas/experiment.py run \
    --build "$LAB/results/standalone-cas-build-new" --out "$LAB/results/standalone-cas-$mode-repeat-new" \
    --reservation-root "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 bridge/experiments/standalone_cas/audit.py --build "$LAB/results/standalone-cas-build-new" \
  --runs "$LAB/results/standalone-cas-wrong-client-new" "$LAB/results/standalone-cas-wrong-cert-new" \
    "$LAB/results/standalone-cas-wrong-library-new" "$LAB/results/standalone-cas-native-new" \
    "$LAB/results/standalone-cas-native-repeat-new" "$LAB/results/standalone-cas-optin-new" \
    "$LAB/results/standalone-cas-optin-repeat-new"
python3 bridge/experiments/standalone_cas/mutation_audit.py --optin "$LAB/results/standalone-cas-optin-new"
```

The loader affects only its launched child; it does not change global dyld
settings, system frameworks, drivers, OCLP or firmware. Do not submit another
GPU host while a reservation is unresolved.
