# Automatic render-encoder factories with the Apple storyboard

The local Apple renderer adaptation now activates the existing queue-local
[automatic render factory](AUTOMATIC_RENDER_FACTORIES.md). Its normal render
path calls the sample's ordinary public
`[commandBuffer renderCommandEncoderWithDescriptor:]`; it no longer invokes
KeplerMetal's explicit render-encoder constructor for each frame. The scope,
shader registration, pipeline and family-assertion bypass still require
explicit local adaptation. A separate negative preflight deliberately calls the
explicit constructor with an unsupported pass to verify refusal.

Two adapted processes, two direct processes and two blank controls each render
eight frames from the original hash-pinned Apple storyboard and locally adapted
controller and renderer. The [auditor](apple-automatic-storyboard-validation.json)
checks 48 frames, 147,456 pixels, 24,576 guard bytes, 240 adapted packets,
two short vertex-binding refusals and 16 invalid depth-store refusals. Direct
and adapted images match across two aspect states and a mesh replacement; blank
images are uniform. Each adapted run records eight client encoder creations
and 16 internal uncommitted recording encoders through the automatic factory,
plus 16 materializations and 104 record reuses. These are operation counts,
not a performance measurement.

The host checks that the queue instance changes class while opted in, returns
to its original class after restoring the scope, and that the IMPs of three
native NVIDIA class methods (queue `commandBuffer`, command-buffer render
factory and render-encoder ICB execution) remain unchanged before, during and
after each run. This is a bounded process-local check, not an audit of every
class or thread. All 83 pinned system-file hashes remain unchanged.

The original application executable is not run, the reported GPU family is
not spoofed, and the application's family assertion is bypassed only in the
local test copy. Visible screen presentation, arbitrary application support,
concurrent restoration, complete ICB behavior and full system integration
remain unproved. No timing or performance gain is claimed. A previous six-run
exploratory cohort before the IMP/restoration instrumentation is preserved and
excluded from this result.

## Reproduce

Prepare the exact Apple archive, local source and metallib using
[APPLE_CPU_ICB_GAP.md](APPLE_CPU_ICB_GAP.md). Build and run on the qualified
x86_64 macOS environment, with a graphical session. The test briefly displays
an instrumented sample window. Use fresh directories and serialize GPU work.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-auto-view-new
A="$PWD/build/apple-auto-view-new"
E=bridge/experiments/apple_automatic_storyboard
B="$LAB/results/apple-auto-view-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-auto-view-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-auto-view-direct-1-new" "$LAB/results/apple-auto-view-auto-1-new" "$LAB/results/apple-auto-view-direct-2-new" "$LAB/results/apple-auto-view-auto-2-new" "$LAB/results/apple-auto-view-blank-1-new" "$LAB/results/apple-auto-view-blank-2-new" --out "$LAB/results/apple-auto-view-audit-new.json"
```
