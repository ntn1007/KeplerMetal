# Conditional CAS: GTX and M1 reference

One public Metal shader runs a local `atomic_compare_exchange_weak` only for
selected threads. Each thread owns a separate threadgroup atomic, so this test
does not rely on a shared CAS winner. Barriers remain outside the conditional.
Four input patterns select no threads, all threads, alternating threads or the
first half of each group. The output includes the returned expected value,
success flag, final atomic value and an activity/guard witness. A separate CPU
oracle allows weak-CAS spurious failure and verifies surrounding buffer guards.

The same source was compiled separately on each machine; the resulting native
programs are not assumed identical. Each run covers 48 dispatches: groups of
33, 128 and 1,024 threads, three groups, two comparison variants and two seeds.

| Execution | Checked output words | Incorrect returned expected values | Other checked mismatches |
| --- | ---: | ---: | ---: |
| GTX 880M, run 1 | 227,520 | 14,226 active; 0 inactive | 0 |
| GTX 880M, run 2 | 227,520 | 14,226 active; 0 inactive | 0 |
| M1 Max reference | 227,520 | 0 | 0 |

On the GTX, all reported expected-value mismatches occurred when an active
thread compared against a different initial value. The equal-comparison and
inactive-thread outputs matched their oracle in these runs. The success flag,
final value, activity/guard witness and buffer guards also matched. This is a
bounded observation; output witnesses do not trace the physical instructions
executed by each lane or prove a general SIMT/reconvergence rule.

The M1 ran macOS 27.2 build 26B118; the iMac ran macOS 26.7.1 build 25G241.
Sources were transferred over the previously configured SSH connection and
verified by SHA-256 before and after the M1 run. The M1's 48 raw output files
were copied back and independently checked on the iMac. The same oracle
classified five deliberate raw-output mutations correctly and refused a
truncated output. M1 and GTX GPU times were not compared.

## Compiler boundary

An additional isolated GTX process captured the native compiler output for
the **same library**, without a user GPU dispatch. The pinned offline decoder
shows a register-indirect branch at `0x290` and a later CAS lock sequence at
`0x3a8`. The existing AIR contract refuses this shader because its expected
value does not follow the currently supported direct vector-insertion form;
the experimental register-flow analysis separately refuses the indirect branch.
These are two distinct barriers to generalization. The capture is from a
separate pipeline construction and does not read resident GPU instructions
from the preceding test processes.

No repair, new Metal feature, certificate or performance improvement is claimed
by this experiment. The NVIDIA driver, Apple frameworks and OCLP were not
modified. The iMac's GPU runs and capture used the cooperative reservation;
the reference used the separate M1 GPU and did not share that reservation.
The signed host, compiled libraries, native output and raw readbacks remain in
the lab. [Sanitized cross-machine audit](cas-divergence-validation.json) ·
[Oracle mutation checks](cas-divergence-mutation-validation.json).

## Reproduction

Choose fresh paths in the existing isolated lab. On the iMac, from this checkout:

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
BUILD="$LAB/results/cas-divergence-build-new"
mkdir "$BUILD"
cp "$REPO/bridge/experiments/cas_divergence/shader.metal" "$BUILD/shader.metal"
cp "$REPO/bridge/experiments/cas_divergence/host.mm" "$BUILD/host.mm"
xcrun metal -std=macos-metal2.4 -fno-fast-math -c "$BUILD/shader.metal" -o "$BUILD/shader.air"
xcrun metallib "$BUILD/shader.air" -o "$BUILD/shader.metallib"
clang++ -arch x86_64 -O2 -std=c++17 -fno-objc-arc "$BUILD/host.mm" -framework Metal -framework Foundation -o "$BUILD/host"
for n in 1 2; do
  OUT="$LAB/results/cas-divergence-gtx-$n-new"
  python3 "$REPO/bridge/experiments/cas_divergence/run_imac.py" --lab "$LAB" --build "$BUILD" --out "$OUT"
  python3 "$REPO/bridge/experiments/cas_divergence/verify.py" --report "$OUT/report.json" --outputs "$OUT/outputs" --out "$OUT/verified.json"
done
CAPTURE="$LAB/results/cas-divergence-capture-new"
python3 "$REPO/bridge/experiments/cas_divergence/capture_imac.py" --lab "$LAB" --library "$BUILD/shader.metallib" --out "$CAPTURE"
python3 "$REPO/bridge/experiments/cas_divergence/analyze_capture.py" --lab "$LAB" --capture "$CAPTURE" --out "$LAB/results/cas-divergence-analysis-new"
```

The capture uses the existing locally built compiler-output observer and
AIR/decoder dependencies. `analyze_capture.py` is intentionally pinned to
the captured instruction offsets and refuses a changed compiler profile;
do not change the pins merely to force a pass. Its result cannot authorize an
import. The iMac runners wait for their signed children without killing or
retrying them; inspect any unresolved child before continuing. The reservation
does not exclude WindowServer or unrelated workloads.

For a fresh M1 reference, transfer `shader.metal`, `host.mm` and `verify.py`
to a new private directory, verify their SHA-256 values on both Macs, and
build the same source with the M1's own Metal toolchain and `clang++` (omit
`-arch x86_64`). Sign the host ad hoc, run it with the device name `M1 Max`,
then run `verify.py` on its report and output directory. The historical
cross-machine `audit.py` checks the exact retained M1 report and capture
fingerprints; a different boot, compiler or run requires review rather than
silently replacing those identities.
