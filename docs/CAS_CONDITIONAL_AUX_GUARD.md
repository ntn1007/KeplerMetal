# Exact conditional CAS auxiliary-section guard

The explicitly adapted conditional-CAS SDK profile now checks the *live*
NVIDIA constructor input for exactly one `0x10006` section of 12 bytes with
SHA-256 `6b6731dc9464fd825d2aefe82c37334875811491ee9c774bae6460f0008949ef`.
This is in addition to its existing original-code and native-metadata checks.
When the auxiliary check fails, the original constructor input is passed
unchanged, the experimental pipeline is rejected and the caller does not
submit a GPU dispatch. The guard applies only to the fingerprinted conditional
profile; it does not declare a general indirect-branch recognizer.

Two independently rebuilt SDK cohorts each verified 56,904 active CAS
operations and 455,040 output words across two repaired processes, with no
differences. Their native controls retained the known expected-value defect.
Each cohort also passed five existing negative controls. In all four repaired
imports the recorded live auxiliary-section check succeeded. The shared
cooperative GPU reservation was used for all iMac hosts.

An additional test-only executable changes **the expected digest in a copied
guard**, leaving the actual NVIDIA constructor input untouched. That mismatch
was observed at the live constructor: no replacement was applied, the
experimental pipeline was refused, the constructor hook was restored and no
user GPU dispatch occurred. Separately, a CPU test of the real guard rejects a
mutation at each of the 12 actual section bytes, missing or duplicate section
counts and wrong lengths. The GPU test is not a claim that mutated native bytes were
passed to the driver.

The prior copied-lock and legacy CAS profiles were rerun as regressions. The
complete source-only build and 70 CAS tests passed. This gate establishes byte
identity in the constructor input, not a live `c0` binding, branch semantics,
resident GPU instructions, transparent application support, or a speedup.
The macOS driver and OCLP were not modified.

[First GPU cohort](cas-conditional-aux-validation.json) ·
[Rebuilt cohort](cas-conditional-aux-reproduction-validation.json) ·
[Constructor guard audit](cas-conditional-aux-guard-validation.json) ·
[Rebuilt guard audit](cas-conditional-aux-guard-reproduction-validation.json) ·
[Copied-lock regression](cas-conditional-aux-copy-validation.json) ·
[Legacy regression](cas-conditional-aux-legacy-validation.json)

## Reproduce

First run the full cohort in [the SDK reproduction](CAS_DIVERGENCE_SDK.md)
with fresh output paths and retained local, pinned dependencies. The runner
uses a cooperative lease, immutable signed hosts and no automatic kill or retry.
Investigate an unresolved process before another GPU test. Then, with the same
`LAB`, `REPO`, `BUILD` and output paths from that reproduction:

```sh
set -e
BAD="$LAB/results/cas-conditional-aux-negative-build-new"
NEG="$LAB/results/cas-conditional-aux-negative-new"
python3 "$REPO/bridge/experiments/cas_divergence/prepare_aux_negative.py" \
  --lab "$LAB" --build "$BUILD" --out "$BAD"
python3 "$REPO/bridge/experiments/cas_divergence/run_sdk.py" \
  --lab "$LAB" --build "$BAD" --out "$NEG" --mode negative-aux
python3 "$REPO/bridge/experiments/cas_divergence/audit_aux_guard.py" \
  --build "$BUILD" --negative-build "$BAD" --negative-run "$NEG" \
  --positive-runs "$LAB/results/cas-conditional-sdk-repaired1-new" \
  "$LAB/results/cas-conditional-sdk-repaired2-new" \
  --out "$LAB/results/cas-conditional-aux-guard-audit-new.json"
python3 -m unittest discover -s "$REPO/tests" -p 'test_cas_conditional_aux.py' -v
```

The binary payloads and local certificates remain in the lab. Only sources,
fingerprints and sanitized results are published.
