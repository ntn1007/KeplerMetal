# Conditional CAS CB0 GPU witness

An isolated, explicitly adapted test process reads `c0[0]`, `c0[4]` and
`c0[8]` on the GTX 880M and writes them to its own output buffer. Two runs,
each with 99 GPU threads, returned `0x298`, `0x2b8` and `0x330` for every
thread. Those values match the three words in the pinned `0x10006` section
from the captured NVIDIA constructor input. Output guards and a per-thread
witness also matched.

This is an instrumented **laboratory witness**, not an unmodified application
or a general Metal feature. Starting from the pinned native shader, the test
redirects its final output store to one appended 64-byte block. That block
loads the three CB0 words, executes the original store unchanged, and returns
to the original exit. Only the original store instruction is replaced in the
original code. The existing native code, metadata and auxiliary-section pins
are checked against the live constructor input before the process-local
import; the constructor hook is restored afterward. The GPU-resident
instructions are not read back.

Before each CB0 run, a separate process uses the same trampoline and store
with three known immediate values instead of CB0 loads. Both controls returned
the correct values for all 99 threads with intact guards and witnesses. Two
separately rebuilt hosts and programs had identical hashes. All four processes
used the common GPU reservation and completed without a kill request. An
independent CPU audit rereads the outputs and the actual candidate section,
checks the signed hosts, decoder replay, instruction delta, input identities,
import receipts and nonoverlapping process intervals. Mutation tests use
temporary copies and no GPU work. [Sanitized audit](cas-cb0-gpu-witness-validation.json) ·
[Audit mutation checks](cas-cb0-gpu-witness-mutation-validation.json).

The observed equality is strong evidence for these three constant reads on
this profile; it does not independently prove the driver's copy mechanism or
that the unmodified shader takes any particular indirect-branch target. The
test uses pattern 0 and does not trace branch execution. Other shader variants,
CB0 offsets, GPU architectures, and contention are unqualified. No performance
measurement, global compiler repair or Metal 3/4 support is claimed. No system
driver, framework or OCLP component was modified.

## Reproduction

The retained NVIDIA capture and toolchain are local prerequisites, not
redistributed. The runner verifies exact source, system, code and decoder
fingerprints and refuses CB0 execution without a completed known-value
control from the same build. Choose fresh output paths. An unresolved child or
reservation must be investigated before another GPU test; nothing is killed or
automatically retried.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
BASE="$LAB/results/cas-conditional-aux-build-20261028-02"
CAPTURE="$LAB/results/cas-divergence-capture-20261028-01"
for n in 1 2; do
  BUILD="$LAB/results/cas-cb0-witness-build-$n-new"
  CONTROL="$LAB/results/cas-cb0-witness-control-$n-new"
  python3 "$REPO/bridge/experiments/cas_divergence/prepare_cb0_readback.py" \
    --lab "$LAB" --base "$BASE" --capture "$CAPTURE" --out "$BUILD"
  python3 "$REPO/bridge/experiments/cas_divergence/run_cb0_readback.py" \
    --lab "$LAB" --build "$BUILD" --out "$CONTROL" --mode control
  python3 "$REPO/bridge/experiments/cas_divergence/run_cb0_readback.py" \
    --lab "$LAB" --build "$BUILD" --out "$LAB/results/cas-cb0-witness-read-$n-new" \
    --mode cb0 --control-run "$CONTROL"
done
python3 "$REPO/bridge/experiments/cas_divergence/audit_cb0_readback.py" \
  --builds "$LAB/results/cas-cb0-witness-build-1-new" "$LAB/results/cas-cb0-witness-build-2-new" \
  --runs "$LAB/results/cas-cb0-witness-control-1-new" "$LAB/results/cas-cb0-witness-read-1-new" \
  "$LAB/results/cas-cb0-witness-control-2-new" "$LAB/results/cas-cb0-witness-read-2-new" \
  --container "$CAPTURE/capture/program-0.compiler-output.bin" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --out "$LAB/results/cas-cb0-witness-audit-new.json"
python3 -m unittest discover -s "$REPO/tests" -p 'test_cas_cb0_readback.py' -v
```

`mutation_cb0_readback_audit.py` accepts the same builds, runs, container and
decoder. It works on temporary copies and never submits a GPU command.
