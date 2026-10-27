# Process-local CAS repair for a default Metal compute descriptor

A second purpose-built client uses `newComputePipelineStateWithDescriptor:options:reflection:error:` exclusively, with a freshly initialized descriptor, no options and no reflection output. It imports no KeplerMetal symbol. An explicitly injected, process-local bootstrap admits only this exact signed executable, its pinned library and the certified functions, on the qualified GTX 880M profile. It routes four certified functions through the existing native CAS repair; a fifth semantic control remains native. The same signed client and library are used in native and opt-in runs.

The bootstrap checks descriptor properties against default values, including buffer mutability and stage input layout, and compares the resulting pipeline's maximum threadgroup size, execution width and static threadgroup memory with a native descriptor-created pipeline. The certified pipeline must be built first. These checks are specific to this pinned executable and system profile, not a complete equivalence proof for arbitrary descriptors. An unsupported descriptor, options or reflection request is forwarded to the native path without repair. Only the nondefault maximum-thread count was exercised as an unsupported-descriptor control; options and reflection rejection are implemented but not separately exercised. Unsupported concurrent creation, async factories, hardened clients and arbitrary programs remain unqualified.

## Evidence

Eight signed, terminal processes ran serially with the cooperative laboratory reservation. Two native and two opt-in hosts each submitted 90 command buffers. On the GTX, the two native runs produced **170,424 expected-value errors** in the four defective functions. The two opt-in runs produced **213,300 correct CAS operations**, including the unchanged semantic controls, independently compared with a CPU oracle. Every run retained 11,520 guard bytes. Changed-client and changed-certificate controls were rejected before dispatch; a different library and a nondefault thread-limit descriptor remained native and did not dispatch. A CPU-only audit also rejects five intentional mutations of output, dispatch metadata, import proof, trace and reservation.

[Machine-readable audit](descriptor-cas-validation.json) · [Mutation checks](descriptor-cas-mutation-validation.json) · [Earlier function-factory experiment](STANDALONE_CAS.md)

The first development build incorrectly assumed some default descriptor properties were nil; it forwarded all functions to native and the oracle refused its result. A later build attempted native pipeline creation before certified creation; the certified import refused the first function and the process exited before dispatch. Building the certified pipeline first resolved the observed failure; the cause of the earlier refusal has not been independently established. These failed runs remain in the laboratory. No system driver or OCLP was changed; no performance improvement or broad Metal support is claimed.

## Reproduction

Use the local qualified `SDK`, its original `SHADER` source, the shared lab root `LAB`, and the current GTX registry ID `RID`; see [the previous experiment](STANDALONE_CAS.md) for these prerequisites. All output paths must be fresh. Run serially, stopping at any error or unresolved reservation:

```sh
(
set -e
python3 bridge/experiments/descriptor_cas/experiment.py build \
  --sdk "$SDK" --shader "$SHADER" --out "$LAB/results/descriptor-build-new"
for mode in wrong-client wrong-cert wrong-library wrong-descriptor native optin; do
  python3 bridge/experiments/descriptor_cas/experiment.py run \
    --build "$LAB/results/descriptor-build-new" --out "$LAB/results/descriptor-$mode-new" \
    --reservation-root "$LAB" --registry-id "$RID" --mode "$mode"
done
for mode in native optin; do
  python3 bridge/experiments/descriptor_cas/experiment.py run \
    --build "$LAB/results/descriptor-build-new" --out "$LAB/results/descriptor-$mode-repeat-new" \
    --reservation-root "$LAB" --registry-id "$RID" --mode "$mode"
done
python3 bridge/experiments/descriptor_cas/audit.py --build "$LAB/results/descriptor-build-new" \
  --runs "$LAB/results/descriptor-wrong-client-new" "$LAB/results/descriptor-wrong-cert-new" \
    "$LAB/results/descriptor-wrong-library-new" "$LAB/results/descriptor-wrong-descriptor-new" \
    "$LAB/results/descriptor-native-new" "$LAB/results/descriptor-native-repeat-new" \
    "$LAB/results/descriptor-optin-new" "$LAB/results/descriptor-optin-repeat-new"
python3 bridge/experiments/descriptor_cas/mutation_audit.py --optin "$LAB/results/descriptor-optin-new"
)
```

The lease excludes cooperating lab runners, not WindowServer or unrelated applications. Constructor-payload evidence and numerical GPU validation are separate checks. This work is an experiment toward integration, not a system driver or a transparent fix for existing applications.
