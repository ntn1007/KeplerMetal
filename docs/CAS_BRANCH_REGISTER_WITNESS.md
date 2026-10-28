# Conditional CAS indirect-branch register witness

A process-local instrumented shader records the **low byte of the branch
register immediately before a relocated indirect branch**. Two independently
rebuilt cohorts each ran four native/witness pairs on the GTX 880M, with 99
threads per process:

| Input pattern | Observed byte in each witness thread | Interpretation |
| --- | --- | --- |
| 0 | `0x01` | Initialized marker remained; the instrumented branch was not observed. |
| 2 | `0x98` | Matches the low byte of the first previously observed CB0 word `0x298`. |
| 3 | `0xb8` | Matches the low byte of `0x2b8`. |
| 4 | `0x30` | Matches the low byte of `0x330`. |

The witness replaces two original instructions: the indirect branch is
redirected to an appended block that stores the low byte of `$r1` in an
already allocated per-thread local byte, then executes a reassembled
`bra $r1 0x0`; the final output store is redirected to a second appended
block that loads that byte into the second output component, replays the
original store and returns to the original exit. The pinned offline decoder
checks both redirects, the relocated branch and store. The native listing
shows that the local byte used by the witness was initialized and otherwise
not explicitly read or written by the original program. The GPU-resident
instructions were not read back.

For every pair, the other three output components and guard bytes matched
the corresponding native baseline and a CPU oracle. The control pattern 0
retained marker 1 for every thread. Imports checked the original code, native
metadata and auxiliary section; all constructor hooks were restored and all
processes terminated without a kill request. The two builds produced identical
host and witness-code hashes. An offline audit checks both cohorts and the
captured bytes. Synthetic tests and audit mutation checks run on the CPU.
[Sanitized audit](cas-branch-register-validation.json) ·
[Audit mutation checks](cas-branch-register-mutation-validation.json).

An earlier offline assembly attempt rejected the local-load syntax before
any GPU run. The successful build uses the explicit `ca` load qualifier; the
failed build remains in the local lab.

These observations cover the **low byte** at the relocated branch, not the
full register or the destination actually entered. Matching bytes and correct
outputs do not prove every original branch path, indirect-target semantics,
or behavior of arbitrary shaders. Pattern 4 is a deliberately tested input
outside the earlier four-pattern qualification. This does not authorize a
general repair, transparent application support, or a performance claim. The
system driver and OCLP were not modified.

## Reproduce

The pinned local capture, decoder, assembler and CB0 witness build are
required; proprietary inputs and raw outputs are not redistributed. Every
process uses the common cooperative reservation and a new signed executable.
No process is killed or retried automatically. Resolve an unresolved process
before further GPU work.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
BASE="$LAB/results/cas-cb0-readback-build-20261028-01"
ANALYSIS="$LAB/results/cas-divergence-analysis-20261028-01"
RUN="$REPO/bridge/experiments/cas_divergence/run_branch_witness.py"
for n in 1 2; do
  BUILD="$LAB/results/cas-branch-build-$n-new"
  python3 "$REPO/bridge/experiments/cas_divergence/prepare_branch_witness.py" \
    --lab "$LAB" --base "$BASE" --analysis "$ANALYSIS" --out "$BUILD"
  B0="$LAB/results/cas-branch-baseline0-$n-new"
  T0="$LAB/results/cas-branch-trace0-$n-new"
  python3 "$RUN" --lab "$LAB" --build "$BUILD" --out "$B0" --mode baseline --pattern 0
  python3 "$RUN" --lab "$LAB" --build "$BUILD" --out "$T0" --mode trace --pattern 0 --baseline "$B0"
  for pattern in 2 3 4; do
    B="$LAB/results/cas-branch-baseline${pattern}-$n-new"
    python3 "$RUN" --lab "$LAB" --build "$BUILD" --out "$B" --mode baseline --pattern "$pattern"
    python3 "$RUN" --lab "$LAB" --build "$BUILD" --out "$LAB/results/cas-branch-trace${pattern}-$n-new" \
      --mode trace --pattern "$pattern" --baseline "$B" --control-baseline "$B0" --control-trace "$T0"
  done
done
python3 "$REPO/bridge/experiments/cas_divergence/audit_branch_witness.py" \
  --builds "$LAB/results/cas-branch-build-1-new" "$LAB/results/cas-branch-build-2-new" \
  --runs "$LAB/results/cas-branch-baseline0-1-new" "$LAB/results/cas-branch-trace0-1-new" \
  "$LAB/results/cas-branch-baseline2-1-new" "$LAB/results/cas-branch-trace2-1-new" \
  "$LAB/results/cas-branch-baseline3-1-new" "$LAB/results/cas-branch-trace3-1-new" \
  "$LAB/results/cas-branch-baseline4-1-new" "$LAB/results/cas-branch-trace4-1-new" \
  "$LAB/results/cas-branch-baseline0-2-new" "$LAB/results/cas-branch-trace0-2-new" \
  "$LAB/results/cas-branch-baseline2-2-new" "$LAB/results/cas-branch-trace2-2-new" \
  "$LAB/results/cas-branch-baseline3-2-new" "$LAB/results/cas-branch-trace3-2-new" \
  "$LAB/results/cas-branch-baseline4-2-new" "$LAB/results/cas-branch-trace4-2-new" \
  --original-listing "$ANALYSIS/native.asm" --decoder "$LAB/build/envydis-only/envydis/envydis" \
  --out "$LAB/results/cas-branch-audit-new.json"
python3 -m unittest discover -s "$REPO/tests" -p 'test_cas_branch_witness.py' -v
```

`mutation_branch_witness_audit.py` accepts the same builds, runs, original
listing and decoder, and modifies only temporary copies without GPU dispatch.
