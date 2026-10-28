# Exact conditional CAS profile through the experimental SDK

The application-local `KPCreateCertifiedNativeCASPipeline` accepts the exact
conditional CAS shader qualified in [the earlier experiment](CAS_DIVERGENCE_REPAIR.md).
The library, original NVIDIA program, replacement and native metadata are each
pinned by SHA-256. The live constructor metadata and original program must
match the certificate before the replacement is imported. The application must
explicitly use the experimental SDK; this does not patch the installed driver
or transparently repair arbitrary Metal clients.

The general AIR contract and SASS flow recognizers **both refuse** this shader.
The certificate records those refusals and identifies the profile as manually
qualified against exact bytes and bounded GPU results. The `candidate` field
does not mean that the general recognizers approved it. Offsets and register
numbers are specific to this program. A changed library, original, replacement,
metadata, profile or claimed AIR verdict is refused; hashes establish byte
identity, not certificate authenticity.

## Evidence and boundaries

In each SDK cohort, two repaired processes ran 48 configurations apiece on the
GTX 880M: 56,904 active CAS operations and 455,040 output words were checked
against a CPU oracle with zero differences. A native control retained 14,226
incorrect expected-value words. Five negative cases were rejected before the
native constructor and before GPU dispatch. The cases cover changed original
code, NOP instead of the repair, unknown profile, changed metadata and a false
AIR qualification claim. The previously captured M1 reference is checked by
the oracle but was not rerun for this experiment.

Each thread uses its own atomic: contention on a single atomic remains
untested. Import receipts validate code and metadata at the constructor; they
do not read back resident GPU instructions. There is no performance benchmark
or claim of general Metal 3/4 support. The existing NVIDIA/Apple drivers and
OCLP were not modified.

The rebuilt SDK also passed the earlier copied-lock profile regression: 22,482
correct CAS operations across seven GPU processes and four pre-constructor
refusals. The legacy candidate regression checked 106,650 correct operations
in its repaired/control run; its native control preserved the expected defect.
The auditor's offline mutation checks reject altered output, guard bytes,
metadata evidence, negative-control constructor entry and unresolved process
state. The complete source-only build and 47 CAS unit tests also pass.

[First SDK cohort](cas-conditional-sdk-validation.json) ·
[Rebuilt SDK cohort](cas-conditional-sdk-reproduction-validation.json) ·
[Previous copied-lock profile](cas-conditional-sdk-copy-regression-validation.json) ·
[Legacy profiles](cas-conditional-sdk-legacy-validation.json) ·
[Auditor mutation tests](cas-conditional-sdk-mutation-validation.json)

## Reproduction on the pinned iMac

The retained library, NVIDIA capture, original GPU audits, decoder, assembler,
and shared GPU reservation module are local prerequisites and are not
redistributed. The preparer checks their pinned fingerprints; an environment
change needs investigation rather than silent repinning. Every output directory
must be fresh. The reservation coordinates cooperating lab runners only; it
does not exclude WindowServer or unrelated processes. An unresolved process
must be investigated before further GPU work; runners do not kill or retry it.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
BUILD="$LAB/results/cas-conditional-sdk-build-new"
python3 "$REPO/bridge/experiments/cas_divergence/prepare_sdk.py" \
  --lab "$LAB" --capture "$LAB/results/cas-divergence-capture-20261028-01" \
  --analysis "$LAB/results/cas-divergence-analysis-20261028-01" \
  --proof "$LAB/results/cas-divergence-repair-audit-20261028-01.json" \
  --reproduction-proof "$LAB/results/cas-divergence-repair-reproduction-audit-20261028-01.json" \
  --out "$BUILD"
RUNNER="$REPO/bridge/experiments/cas_divergence/run_sdk.py"
VERIFY="$REPO/bridge/experiments/cas_divergence/verify.py"
for item in negative-pin:negative-pin negative-nop:negative-nop negative-profile:negative-profile negative-metadata:negative-metadata negative-air:negative-air native:native repaired:repaired1 repaired:repaired2; do
  mode=${item%:*}; label=${item#*:}; OUT="$LAB/results/cas-conditional-sdk-$label-new"
  python3 "$RUNNER" --lab "$LAB" --build "$BUILD" --out "$OUT" --mode "$mode"
  if test "$mode" = native || test "$mode" = repaired; then
    python3 "$VERIFY" --report "$OUT/report.json" --outputs "$OUT/outputs" --out "$OUT/verified.json"
  fi
done
python3 "$REPO/bridge/experiments/cas_divergence/audit_sdk.py" --build "$BUILD" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --reference "$LAB/results/cas-divergence-m1-20261028-01" \
  --runs "$LAB/results/cas-conditional-sdk-negative-pin-new" "$LAB/results/cas-conditional-sdk-negative-nop-new" \
  "$LAB/results/cas-conditional-sdk-negative-profile-new" "$LAB/results/cas-conditional-sdk-negative-metadata-new" \
  "$LAB/results/cas-conditional-sdk-negative-air-new" "$LAB/results/cas-conditional-sdk-native-new" \
  "$LAB/results/cas-conditional-sdk-repaired1-new" "$LAB/results/cas-conditional-sdk-repaired2-new" \
  --out "$LAB/results/cas-conditional-sdk-audit-new.json"
```

`mutation_sdk_audit.py` accepts the same build, decoder, reference and eight
runs; it mutates temporary copies without dispatching GPU work. The local
certificate contains captured proprietary bytes and must not be published.
