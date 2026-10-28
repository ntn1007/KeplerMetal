# Conditional CAS: joint branch and target witness

Two independently built instrumented programs were each run in four fresh,
signed GTX 880M processes (99 threads per process). In each thread, the witness
stores the low byte of the register at the **relocated** indirect branch into
an existing initialized local byte. Entry at `0x330` increments that byte,
then replays the displaced original instruction. At output, the modified byte
replaces one result component; all other components and guards are compared
with a native baseline and CPU oracle. The other two target locations remain
unmodified. A local byte is not a general event log: later writes can obscure
earlier events, and repeated entry would increment the marker again.

| Pattern | Marker | Threads | Observation in this instrumented program |
| --- | --- | ---: | --- |
| 0 | `0x02` | 99 | Initial value 1 incremented at `0x330`; no branch marker persisted. |
| 2 | `0x98` | 51 | Branch-register low byte persisted without an observed increment. |
| 2 | `0x99` | 48 | Low byte `0x98` plus one increment persisted. |
| 3 | `0xb8` | 99 | Branch-register low byte persisted without an observed increment. |
| 4 | `0x31` | 99 | Low byte `0x30` plus one increment persisted. |

Both cohorts have identical histograms. The joint markers also match, for each
thread, the sum of the earlier separately audited branch-register marker and
the earlier separately audited `0x330` entry marker. Those earlier results were
obtained in different processes; the new witness correlates both markers in
one instrumented process. The comparison uses hashes from the earlier audit
receipts, and all native baselines pass the CPU oracle. All eight new
processes terminated; signed binaries, constructor receipts, input hashes,
system profile, code changes and nonoverlapping GPU trace intervals are
rechecked by [the sanitized audit](cas-joint-witness-validation.json).

The witness does **not** prove the origin of entry at `0x330`. The captured
listing includes a direct branch from `0x2b0` to `0x330`, and there may be
other routes. The branch is relocated for instrumentation, the GPU-resident
instructions were not read back, and only the branch-register low byte is
recorded. No claim is made about all control paths, generic CAS repair,
transparent integration or speed. No system driver or OCLP change was made.

## Reproduction

The pinned native capture and offline tools are required locally; they are
not redistributed. Reproduce the prior branch and target witness cohorts and
their audits first, as described in [branch witness](CAS_BRANCH_REGISTER_WITNESS.md)
and [target witness](CAS_TARGET_ENTRY_WITNESS.md). Use fresh lab paths. These
commands use Bash or zsh arrays, not POSIX `sh`. Every GPU process takes the
shared reservation; never kill or retry an unresolved process automatically.

```bash
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
BASE="$LAB/results/cas-cb0-readback-build-20261028-01"
ANALYSIS="$LAB/results/cas-divergence-analysis-20261028-01"
DIR="$REPO/bridge/experiments/cas_divergence"
builds=(); baselines=(); runs=(); branches=(); targets=()
for n in 1 2; do
  BUILD="$LAB/results/cas-joint-build-$n-new"; builds+=("$BUILD")
  python3 "$DIR/prepare_joint_witness.py" --lab "$LAB" --base "$BASE" --analysis "$ANALYSIS" --out "$BUILD"
  B0="$LAB/results/cas-branch-baseline0-$n-new"
  T0="$LAB/results/cas-joint-trace0-$n-new"
  for pattern in 0 2 3 4; do
    B="$LAB/results/cas-branch-baseline${pattern}-$n-new"
    T="$LAB/results/cas-joint-trace${pattern}-$n-new"
    baselines+=("$B"); runs+=("$T")
    branches+=("$LAB/results/cas-branch-trace${pattern}-$n-new")
    targets+=("$LAB/results/cas-target-330-trace${pattern}-$n-new")
    if [ "$pattern" = 0 ]; then
      python3 "$DIR/run_joint_witness.py" --lab "$LAB" --build "$BUILD" --out "$T" --mode trace --pattern 0 --baseline "$B"
    else
      python3 "$DIR/run_joint_witness.py" --lab "$LAB" --build "$BUILD" --out "$T" --mode trace --pattern "$pattern" \
        --baseline "$B" --control-baseline "$B0" --control-trace "$T0"
    fi
  done
done
python3 "$DIR/audit_joint_witness.py" --builds "${builds[@]}" --baselines "${baselines[@]}" \
  --runs "${runs[@]}" --branch-runs "${branches[@]}" --target-runs "${targets[@]}" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --original-listing "$ANALYSIS/native.asm" \
  --branch-audit "$LAB/results/cas-branch-audit-new.json" --target-audit "$LAB/results/cas-target-entry-audit-new.json" \
  --out "$LAB/results/cas-joint-audit-new.json"
python3 -m unittest discover -s "$REPO/tests" -p 'test_cas_joint_witness.py' -v
```
