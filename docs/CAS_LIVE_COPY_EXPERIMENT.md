# Targeted native CAS repair with a copied lock result

This experiment covers one NVIDIA-compiled weak-CAS shader that the current
general candidate recognizer refuses. Unlike the earlier certified shapes, its
lock result is copied from one register to another before the success comparison;
the first instruction after that comparison is a constant-bank move, not a
barrier. The test shader dynamically selects one of four shared-memory atomics
and checks all three neighboring elements as sentinels.

For this **one byte-pinned program**, a process-local import replaces one
instruction with a branch to an appended block. The block replays the displaced
constant-bank move, copies the saved lock result into the expected-value output
register, and returns. The other original code and every original schedule
word remain unchanged. A control differs from the repaired program only in
replacing the corrective move with a NOP. The disassembly and register roles
are profile-specific observations, not a recipe for rewriting arbitrary shaders.

## GTX evidence

On the pinned GTX 880M and NVIDIA driver profile `e240d54a…`, 12 signed,
serial processes performed 36 compute dispatches and checked raw readbacks.
Six corrected processes produced **4,347 correct CAS operations**, including
unequal comparisons and contended equal comparisons, at 33 and 128 threads per
group. Each run used three groups and three seeds; source-level indices 0–3
were covered. The CPU auditor independently checked all four output words and
the surrounding guards. This verifies the sentinel expression, not physical
address tracing.

Three native runs, two NOP-trampoline controls and one original-code replay
retained **2,619 incorrect expected-value words**; the other checked output
fields were correct. A wrong-original-code pin was rejected during pipeline
construction before GPU dispatch. Imported cases confirm the original native
constructor input and replacement payload, restoration of the constructor,
and preservation of native metadata except the instruction count. They do
not read resident GPU instruction memory. The auditor also verifies the
individual signed host identities and nonoverlapping terminal reservations.

A second host built from the same sources had a different unsigned executable
hash. Its negative control, NOP control and corrected 33-thread run produced
six raw readbacks identical to the corresponding first-host readbacks. The
complete 13-process cohort was then repeated with the source recipe and passed
the same independent numerical and lifecycle audit. These are separate runs,
not a claim that the unsigned executables were byte-identical.

This is a **laboratory correction for one shader**, not a change to the installed
compiler, a general dataflow recognizer, an SDK-supported certificate or a
transparent application fix. The [SDK now supports this one pinned profile](CAS_LIVE_COPY_SDK.md);
the generic recognizer still refuses this different displaced-instruction form.
No performance benchmark, new Metal family, or
GPU hardware capability beyond the tested behavior is claimed. No system
driver, framework or OCLP configuration was modified. Existing policies remain
unchanged; do not generalize register numbers or offsets.

[Numerical and process audit](cas-livecopy-validation.json) ·
[Reproduction audit](cas-livecopy-reproduction-validation.json) ·
[Auditor mutation checks](cas-livecopy-mutation-validation.json)

## Reproduce on the pinned laboratory

The retained `dynamic-checked` compiled library and native capture, locally
built pinned `envyas`/`envydis`, common reservation module and the target NVIDIA
profile are prerequisites. They are not distributed. `prepare.py` checks all
required fingerprints, builds an isolated host, constructs the exact original,
repair and NOP programs, and performs no dispatch. Use a fresh output path;
do not alter a pin to force an outcome. The cooperative reservation does not
exclude WindowServer or nonparticipating processes. The runner never kills a
child or retries automatically; investigate any unresolved process before
continuing. The independent auditor currently pins the observed GPU registry
ID and case names; a changed device identity requires review.

Run from the public checkout, then the lab root:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
WORK="$LAB/results/cas-livecopy-reproduction-new"
python3 "$REPO/bridge/experiments/cas_livecopy/prepare.py" --lab "$LAB" --out "$WORK"
cd "$LAB"
export KM_CAS_WORK="$WORK"
RUNNER="$REPO/bridge/experiments/cas_livecopy/run_no_kill.py"
while read -r mode local variant name; do
  python3 "$RUNNER" "$mode" "$local" "$variant" "$name" || break
done <<'CASES'
native 33 1 native-v1-l33
native_trampoline 33 1 trampoline-v1-l33
native_repaired 33 1 repaired-v1-l33
native 33 0 native-v0-l33
native_trampoline 33 0 trampoline-v0-l33
native_repaired 33 0 repaired-v0-l33
native_replay 33 1 replay-v1-l33
native 128 1 native-v1-l128
native_repaired 128 1 repaired-v1-l128
native_repaired 128 0 repaired-v0-l128
negative_native_pin 33 1 negative-pin-v1-l33
native_repaired 33 0 repaired-v0-l33-repeat
native_repaired 128 1 repaired-v1-l128-repeat
CASES
python3 "$REPO/bridge/experiments/cas_livecopy/audit.py" --work "$WORK" --out "$WORK/audit.json"
python3 "$REPO/bridge/experiments/cas_livecopy/mutation_audit.py" --work "$WORK" --out "$WORK/mutation-audit.json"
```
