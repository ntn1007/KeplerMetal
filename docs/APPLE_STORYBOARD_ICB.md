# Apple sample storyboard and view controller with scoped ICBs

The bounded laboratory host now loads the original, hash-pinned Apple sample
storyboard and instantiates its window controller, `AAPLViewController`,
`MTKView`, and `AAPLRenderer`. It uses a small temporary non-key window and
invokes two controlled frames. The separately obtained Apple sources and
compiled storyboard stay in the local lab; neither is included in the public
repository. This is not a run of Apple's original executable.

Two local adaptation scripts modify exact, hash-checked source copies. The
controller still calls the original GPU-family query, which returned NO on the
GTX in all six processes; its assertion is bypassed explicitly for this lab
experiment, without spoofing the `MTLDevice` family. The controller configures
an explicitly paused, readable 64 × 48 view. The renderer opts into the scoped
adapter and supports direct, ICB and blank modes. It captures only its own
render target, waits for each GPU command buffer and ignores automatic layout
draws outside the two requested frames. The host sets the drawable size and
aspect for each measured frame. Full source, UI, controller, lifecycle and
hardware-family compatibility are not established by this instrumented run.

[The auditor](apple-storyboard-icb-validation.json) verifies two direct, two
adapted and two blank processes under the shared GPU reservation: 12 frames,
36,864 pixels, 6,144 guard bytes and 60 adapted draw packets for all 15 actual
generated gear meshes (36–504 vertices). The direct and adapted images are
byte-identical and differ from the uniform blank; four unsupported depth store
actions are refused before the user command buffer is committed. The compiled
storyboard files, source hashes, build, signed executable, process termination
and 83 pinned system files are checked. None of this proves visible screen
presentation, original-executable support, transparent integration, complete
ICB support or a performance gain.

Earlier exploratory launches found a transient 5 × 4 layout drawable. A
bounded diagnostic launch completed one 64 × 48 frame before a later automatic
layout draw failed the size assertion. Those runs are preserved and excluded
from the six-process result. The final host skips those extra callbacks and
resets the explicit size for each controlled draw.

## Reproduce

Prepare the exact Apple archive, local source and metallib using
[APPLE_CPU_ICB_GAP.md](APPLE_CPU_ICB_GAP.md). Build and run on the qualified
x86_64 macOS environment, with a graphical session. The test briefly displays
an instrumented sample window. Use fresh directories and serialize GPU work.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-storyboard-new
A="$PWD/build/apple-storyboard-new"
E=bridge/experiments/apple_storyboard_icb
B="$LAB/results/apple-storyboard-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-storyboard-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-storyboard-direct-1-new" "$LAB/results/apple-storyboard-auto-1-new" "$LAB/results/apple-storyboard-direct-2-new" "$LAB/results/apple-storyboard-auto-2-new" "$LAB/results/apple-storyboard-blank-1-new" "$LAB/results/apple-storyboard-blank-2-new" --out "$LAB/results/apple-storyboard-audit-new.json"
```
