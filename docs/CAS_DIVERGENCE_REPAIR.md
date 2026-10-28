# Exact-profile repair for the conditional CAS experiment

The [conditional CAS reference](CAS_DIVERGENCE_REFERENCE.md) exposed incorrect
returned expected values on the GTX when the comparison fails. This experiment
repairs **that one captured NVIDIA program** inside an explicitly adapted test
process. It uses the existing native-program import and retains the installed
driver and Metal resource management.

The captured program computes the CAS comparison before `0x428`. The repair
replaces the instruction at `0x428` with a branch to an appended 64-byte block.
That block replays the displaced instruction, copies the lock result into the
expected-value register, and returns to the original code. Every other
original eight-byte word, including all original scheduling words, remains
unchanged. A NOP control differs from the repaired program at only the copied
value instruction. The precise registers and offsets are observations for this
fingerprinted program, not a generic rewrite rule.

## GPU results

Two independent seven-process cohorts ran serially on the GTX 880M. Each
cohort includes a wrong-original-pin refusal, one native run, an original-code
replay, two NOP controls and two corrected runs. Each GPU run covers 48
configurations: 33, 128 and 1,024 threads per group; no, all, alternating or
half active; equal/unequal comparisons; three groups and two seeds. Each thread
uses its own shared atomic, so **contention on a single atomic is not tested**.

Per cohort, the two corrected runs checked **56,904 active CAS operations**
and **455,040 output words**, including inactive-thread and guard checks,
with zero mismatches. Each native, replay and NOP run retained 14,226 incorrect
active expected-value words; other checked fields and guards matched. The CPU
oracle independently rereads all raw results and allows weak-CAS spurious
failure. The previously captured M1 Max reference also passes that oracle;
it was not rerun for these cohorts and its GPU code is different.

The wrong original pin was rejected at the native import gate before GPU
dispatch. The successful import receipts verify the original constructor code,
the replacement payload, constructor restoration and native metadata
preservation except instruction count. They do **not** compare the live metadata
against the separately captured metadata, nor read back resident GPU
instructions. The exact input library and code are pinned. On the rebuilt
cohort, the recorded NVIDIA Metal driver, AIR plugin and OCLP plist fingerprints
matched before and after each process. Both cohorts used the same host binary
hash and same repaired program hash. The auditor checks the 8-byte differences,
the pinned decoder, signed processes, raw outputs and the M1 reference; copied
result, guard, import-evidence, process-state and repair mutations are refused.

This is **not a general compiler fix or a system driver release**. The
[experimental SDK](CAS_DIVERGENCE_SDK.md) accepts this exact fingerprinted
profile for an explicitly adapted client; ordinary applications do not receive
the correction. The general AIR diagnosis and indirect-branch analysis still
refuse this shader. No speedup or new Metal family is claimed. Installed Apple
and NVIDIA components, OCLP and firmware were not modified.

[First cohort](cas-divergence-repair-validation.json) ·
[Source rebuild cohort](cas-divergence-repair-reproduction-validation.json) ·
[Auditor mutations](cas-divergence-repair-mutation-validation.json)

## Reproduce on the pinned iMac

The retained library and native capture from the earlier experiment and the
locally built pinned assembler, decoder and reservation module are required.
They are not redistributed. The preparer refuses different inputs and creates
a fresh isolated host. Every runner waits for its signed child without killing
or automatically retrying it. Inspect an unresolved process and reservation
before any further GPU work; the lease does not exclude WindowServer or other
nonparticipating workloads.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
BUILD="$LAB/results/cas-divergence-repair-build-new"
python3 "$REPO/bridge/experiments/cas_divergence/prepare_repair.py" \
  --lab "$LAB" --capture "$LAB/results/cas-divergence-capture-20261028-01" --out "$BUILD"
RUNNER="$REPO/bridge/experiments/cas_divergence/run_repair.py"
VERIFY="$REPO/bridge/experiments/cas_divergence/verify.py"
for item in negative-pin:negative native:native replay:replay trampoline:trampoline1 repaired:repaired1 trampoline:trampoline2 repaired:repaired2; do
  mode=${item%:*}; label=${item#*:}; OUT="$LAB/results/cas-divergence-repair-$label-new"
  python3 "$RUNNER" --lab "$LAB" --build "$BUILD" --out "$OUT" --mode "$mode"
  if test "$mode" != negative-pin; then
    python3 "$VERIFY" --report "$OUT/report.json" --outputs "$OUT/outputs" --out "$OUT/verified.json"
  fi
done
python3 "$REPO/bridge/experiments/cas_divergence/audit_repair.py" --build "$BUILD" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --reference "$LAB/results/cas-divergence-m1-20261028-01" \
  --runs "$LAB/results/cas-divergence-repair-negative-new" "$LAB/results/cas-divergence-repair-native-new" \
  "$LAB/results/cas-divergence-repair-replay-new" "$LAB/results/cas-divergence-repair-trampoline1-new" \
  "$LAB/results/cas-divergence-repair-trampoline2-new" "$LAB/results/cas-divergence-repair-repaired1-new" \
  "$LAB/results/cas-divergence-repair-repaired2-new" --out "$LAB/results/cas-divergence-repair-audit-new.json"
```

The auditor pins the retained M1 reference and GPU registry identity; a changed
boot, compiler, system profile or reference requires review, not a silent
repin. `mutation_repair_audit.py` accepts the same build, decoder, reference and
seven runs and operates on temporary copies without GPU dispatch.
