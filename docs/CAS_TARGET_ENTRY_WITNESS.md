# Conditional CAS: candidate target-entry witnesses

Three separately instrumented programs mark entry at `0x298`, `0x2b8`, or
`0x330`. The original indirect-branch instruction at `0x290` remains
byte-identical in each imported program. Each probe replaces its selected
target instruction with a branch to an appended block that writes a zero byte
to the existing per-thread local marker, executes the displaced original
instruction unchanged and returns. A second redirect reads the marker at the
final output store. The native code's earlier local-byte initialization remains
in place. The existing original-code, metadata and auxiliary-section checks
run at the constructor, whose hook is restored before execution.

The following table reports threads marked as having entered the selected
instrumented location, out of 99. Two independently rebuilt cohorts produced
the same matrix. Each trace is compared with a previously qualified native
baseline for the same input, including a CPU oracle, guards and all three
non-marker output components.

| Probe location | Pattern 0 | Pattern 2 | Pattern 3 | Pattern 4 |
| --- | ---: | ---: | ---: | ---: |
| `0x298` | 0 | 99 | 0 | 0 |
| `0x2b8` | 0 | 0 | 99 | 0 |
| `0x330` | 99 | 48 | 0 | 99 |

This is entry evidence **in the instrumented programs**, not a direct readback
of GPU-resident instructions. The markers alone do not prove that entry came
from the indirect branch. In particular, `0x330` also marks every thread in
the pattern-0 control; the decoded program has other paths to that location.
The [separate branch-register witness](CAS_BRANCH_REGISTER_WITNESS.md)
observed matching low bytes at a relocated branch, but does not by itself
establish entry origin here. No general SIMT, arbitrary-shader or performance
claim follows from the matrix.

All 24 new trace processes were signed, used the cooperative GPU reservation
and terminated without a kill request. Eight earlier, signed baseline
processes are reused only after the host, library, original code, metadata and
system profile match. An independent offline audit checks both cohorts,
decoder replay, two-word code changes, displaced-instruction identity,
constructor receipts, output bytes and nonoverlapping trace intervals.
The first offline builds were refused because the decoder prints `$r63` as
`0x0`; the expectation was corrected before any GPU dispatch. The failed
builds remain in the lab. [Sanitized audit](cas-target-entry-validation.json).

The GPU-resident program was not read back. These are bounded experiments,
not a general driver repair or transparent Metal integration. The installed
driver and OCLP were not modified.

## Reproduce

Requires the pinned local CB0 witness build, original analysis, and two sets
of native baselines produced by [the branch-register experiment](CAS_BRANCH_REGISTER_WITNESS.md).
Use fresh directories and the same cooperative GPU reservation. Never kill or
automatically retry a process; investigate any unresolved child first.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
BASE="$LAB/results/cas-cb0-readback-build-20261028-01"
ANALYSIS="$LAB/results/cas-divergence-analysis-20261028-01"
RUN="$REPO/bridge/experiments/cas_divergence/run_target_entry.py"
builds=(); baselines=(); traces=()
for n in 1 2; do
  for pattern in 0 2 3 4; do baselines+=("$LAB/results/cas-branch-baseline${pattern}-$n-new"); done
  B0="$LAB/results/cas-branch-baseline0-$n-new"
  for target in 298 2b8 330; do
    BUILD="$LAB/results/cas-target-${target}-build-$n-new"; builds+=("$BUILD")
    python3 "$REPO/bridge/experiments/cas_divergence/prepare_target_entry.py" \
      --lab "$LAB" --base "$BASE" --analysis "$ANALYSIS" --target "0x$target" --out "$BUILD"
    T0="$LAB/results/cas-target-${target}-trace0-$n-new"; traces+=("$T0")
    python3 "$RUN" --lab "$LAB" --build "$BUILD" --out "$T0" --mode trace --pattern 0 --baseline "$B0"
    for pattern in 2 3 4; do
      T="$LAB/results/cas-target-${target}-trace${pattern}-$n-new"; traces+=("$T")
      python3 "$RUN" --lab "$LAB" --build "$BUILD" --out "$T" --mode trace --pattern "$pattern" \
        --baseline "$LAB/results/cas-branch-baseline${pattern}-$n-new" --control-baseline "$B0" --control-trace "$T0"
    done
  done
done
python3 "$REPO/bridge/experiments/cas_divergence/audit_target_entry.py" \
  --builds "${builds[@]}" --baselines "${baselines[@]}" --runs "${traces[@]}" \
  --original-listing "$ANALYSIS/native.asm" --decoder "$LAB/build/envydis-only/envydis/envydis" \
  --out "$LAB/results/cas-target-entry-audit-new.json"
python3 -m unittest discover -s "$REPO/tests" -p 'test_cas_target_entry.py' -v
```
