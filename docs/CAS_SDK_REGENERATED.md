# Regenerated native CAS SDK qualification

The optional native CAS SDK can again be built from the current source, with
its complete header dependencies and example client. The builder checks the
installed GeForce Metal driver against the existing qualified profiles before
and after preparation, records the actual digest, and verifies the four local
fixture-source hashes. The example identifies exactly one GTX 880M by Metal
device and PCI vendor/device identity, rather than a registry ID from an older
boot. The ID is still recorded as a per-boot observation.

For this qualification the AIR/SASS diagnosis was rebuilt after the
[disassembly-integrity change](CAS_DISASSEMBLY_COVERAGE.md). Four candidate
certificates reproduce the listing with the pinned local decoder; one valid
original-comparand control is rejected as a repair candidate. The module
builder's explicit `--require-decoder-evidence` gate checks the certificate
markers and driver profile before it creates its output. The marker is
provenance, not a trusted signature: the regenerated results are tied to this
laboratory's recorded inputs and independent checks.

## GTX results

Six serialized client hosts used the same signed, source-built executable:
negative, uncommitted preparation, two native baselines and two repaired runs.
The two repaired runs executed **180 command buffers and 213,300 CAS operations**,
including the unchanged comparand controls; all 853,200 output words and guards
match the independent CPU oracle. Each native baseline reproduces 85,212 wrong
expected-value words in the affected cases, while its success/final/index words
and unchanged comparand controls remain correct. This confirms the behavior
of these tested shaders, not every atomic program or race pattern.

The negative host refused six inputs before entering the constructor and two
at the native original-code/metadata checks. The preparation host constructed
and encoded commands without committing user command buffers. The corrected
client wipes caller-owned library/certificate inputs before commit; the tested
runtime retains what it needs and restores the process-local constructor hook.
No speed benchmark was performed. No installed driver, framework or OCLP change
is claimed, and the decoder replay itself is not a proof of decoder correctness.

The [offline audit](cas-sdk-regenerated-validation.json) replays the CPU oracle,
checks the four certificate/program/metadata pins and the one semantic refusal,
reruns the pinned offline decoder on the captured programs, and checks 21
preparation processes and six client hosts for terminal, nonoverlapping
reservations. The cooperative lease does not exclude WindowServer or other
unrelated GPU users. It also checks the final source rebuild: its executable
and `KeplerNativeCAS.o` bytes are identical to the GPU-tested versions, while
its archive container SHA-256 differs. The certificate-generating preparation
was built from an earlier isolated source snapshot; the final SDK module and
client were rebuilt separately from the current published source. No GPU
qualification is attributed merely to source equivalence.

The initial preparation successfully produced four candidates and one refusal,
but wrote a historical driver digest and omitted the finished example files.
It is retained locally as exploratory evidence and is not the final cohort.
The corrected preparation generated the certificates used here. Existing
certificates are not automatically revoked by the runtime: regenerate and
qualify each one before use. The current runtime does not authenticate an
issuer of arbitrary certificates. These are opt-in application-level repairs,
not a general compiler fix or transparent support for unmodified applications.

## Reproduction

Use the exact qualified iMac profile and an existing laboratory with the source
fixtures, AIR reader objects, assembler, decoder and common reservation root
`LAB`. Those local prerequisites and historical provenance are not supplied by
this repository; obtain vendor dependencies under their applicable terms.
All output paths must be new. The source overlay builder checks fixture hashes,
the decoder pin and the shared launcher's identity; it copies project sources
and keeps vendor/build inputs local. It does not dispatch GPU work.

```sh
OVERLAY="$LAB/results/cas-sdk-overlay-new"
python3 bridge/tools/cas_sdk_source_overlay.py --lab-root "$LAB" --out "$OVERLAY"
python3 "$OVERLAY/tools/prepare_native_cas_sdk.py" --out "$OVERLAY/results/generated"
python3 "$OVERLAY/tools/build_native_cas_sdk_module.py" \
  --assets-from "$OVERLAY/results/generated/KeplerNativeCAS/assets" \
  --out "$OVERLAY/results/current" --require-decoder-evidence
python3 bridge/tools/cas_sdk_qualification.py build \
  --sdk "$OVERLAY/results/current/KeplerNativeCAS" --out "$LAB/results/cas-sdk-client-new"
for mode in negative prepare native execute; do
  python3 bridge/tools/cas_sdk_qualification.py run \
    --build "$LAB/results/cas-sdk-client-new" --out "$LAB/results/cas-sdk-$mode-new" \
    --reservation-root "$LAB" --mode "$mode" || break
done
for mode in native execute; do
  python3 bridge/tools/cas_sdk_qualification.py run \
    --build "$LAB/results/cas-sdk-client-new" --out "$LAB/results/cas-sdk-$mode-repeat-new" \
    --reservation-root "$LAB" --mode "$mode" || break
done
python3 bridge/tools/audit_cas_sdk_qualification.py \
  --generated "$OVERLAY/results/generated" --build "$LAB/results/cas-sdk-client-new" \
  --final-build "$LAB/results/cas-sdk-client-new" --module-overlay "$OVERLAY" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" \
  --runs "$LAB/results/cas-sdk-negative-new" "$LAB/results/cas-sdk-prepare-new" \
    "$LAB/results/cas-sdk-native-new" "$LAB/results/cas-sdk-native-repeat-new" \
    "$LAB/results/cas-sdk-execute-new" "$LAB/results/cas-sdk-execute-repeat-new"
python3 -m unittest discover -s tests -p test_cas_sdk_preflight.py -v
```

The single-overlay recipe above packages the same source and local dependencies;
the complete recipe as a single fresh overlay has not been run. The reported
cohort used the two separately recorded preparation/module overlays described
above. Resolve any failed or uncertain signed process to a terminal reservation
state before submitting another GPU test.
