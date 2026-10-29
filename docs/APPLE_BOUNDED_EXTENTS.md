# Bounded target extents for the Apple Release ICB profile

The scoped Apple Release view profile now accepts each target width and height
from **1 through 4,096 pixels**, preserving the existing format, pipeline,
resource and native-command checks. This is an implementation limit for this
experiment, not a claim about the GPU's maximum texture size. Other shader
profiles keep their previous target constraints.

Eight extents were tested: 1 × 1, 3 × 7, 64 × 48, 127 × 91, 320 × 240,
800 × 600, 2,560 × 1,440 and 4,096 × 4,096. **The intermediate combinations
are admitted by the bounded check but have not been exhaustively tested.**
In particular, this is not general Metal or arbitrary-shader support.

## GPU and contract evidence

Two runs of the unchanged-source Apple Release executable each rendered the
eight extents in one process. Each of their 16 captures matches the
corresponding instrumented direct-draw reference byte for byte. Every capture
checks command-buffer completion, guards and row padding. The application
window was not resized; the test explicitly set drawable sizes, paused the
view, disabled its framebuffer-only flag for readback and inserted a blit.
The pipeline object is still replaced inside the process. Actual visible
presentation and uninstrumented application integration are not proven.

The separate [source-adapted matrix](apple-extent-grid-matrix.json) comprises
six serialized processes, 48 frames, 240 indirect draw records, 126,210,402
pixel values and 474,744 checked row-padding bytes. Direct and adapted
images agree, with blank controls; for the two tiny extents a blank-looking
image alone cannot prove visible geometry. The same ICB is reused across the
eight sizes, and recorded draw commands are checked at each frame.

The [combined audit](apple-bounded-extents-validation.json) also validates
12 no-dispatch target-contract cases, including rejection at 4,097 on either
axis, a wrong color format and the older shader at 800 × 600. A fresh 64 × 48
Apple regression and a separate non-Apple stage-in direct/ICB comparison pass
on the same runtime. The latter checks reference pixel regions on the CPU.
The two original runs use Apple's own bundle-library bytes, not a different
shader compilation. The 83 pinned system-file hashes are a bounded check;
the GPU reservation coordinates participating lab runners only.

The sample's Release assertions, including its Mac 2 family assertion, are
disabled and the device's family is not spoofed. No installed driver, OCLP or
firmware was changed. No performance benchmark or hardware-video execution is
claimed.

## Reproduce

Use the sample, Release bundle, carrier, old shader, historical 64 × 48
direct control and stage-in assets described in
[APPLE_NATURAL_EXTENT.md](APPLE_NATURAL_EXTENT.md). Choose fresh output paths,
run GPU processes serially and resolve any unknown child state before retrying.
The experiments briefly open instrumented windows in the graphical session.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
APP='/path/to/Release/Indirect Command Buffers on CPU.app'
LOG='/path/to/apple-release-build.log'
CARRIER='/path/to/render_state_carrier.metallib'
DEFAULT="$APP/Contents/Resources/default.metallib"
STAGE='/path/to/previous-standalone-inherited-build'
python3 tools/build_from_source.py --out build/apple-extent-grid-new
A="$PWD/build/apple-extent-grid-new"
E=bridge/experiments/apple_extent_grid
B="$LAB/results/apple-extent-grid-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" \
  --legacy "$CARRIER" --vertex "$DEFAULT" --manifest "$E/profiles.json" --out "$B"
idx=0
for mode in direct auto direct auto blank blank; do
  idx=$((idx + 1))
  python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" \
    --out "$LAB/results/apple-extent-grid-$mode-$idx-new"
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --vertex "$DEFAULT" \
  --runs "$LAB/results/apple-extent-grid-direct-1-new" "$LAB/results/apple-extent-grid-auto-2-new" \
         "$LAB/results/apple-extent-grid-direct-3-new" "$LAB/results/apple-extent-grid-auto-4-new" \
         "$LAB/results/apple-extent-grid-blank-5-new" "$LAB/results/apple-extent-grid-blank-6-new" \
  --out "$LAB/results/apple-extent-grid-audit-new.json"
O="$LAB/results/apple-original-extent-grid-build-new"
python3 bridge/experiments/apple_original_extent_grid/experiment.py build --lab "$LAB" --archive "$A" \
  --sample "$S" --release "$APP" --build-log "$LOG" --carrier "$CARRIER" --shader "$DEFAULT" \
  --profiles bridge/experiments/apple_release_library/profiles.json --out "$O"
for n in 1 2; do python3 bridge/experiments/apple_original_extent_grid/experiment.py run --lab "$LAB" --build "$O" --out "$LAB/results/apple-original-extent-grid-$n-new"; done
R="$LAB/results/apple-extent-grid-64-build-new"
python3 bridge/experiments/apple_release_library/experiment.py build --lab "$LAB" --archive "$A" \
  --sample "$S" --release "$APP" --build-log "$LOG" --carrier "$CARRIER" --shader "$DEFAULT" \
  --profiles bridge/experiments/apple_release_library/profiles.json --out "$R"
python3 bridge/experiments/apple_release_library/experiment.py run --lab "$LAB" --build "$R" --out "$LAB/results/apple-extent-grid-64-run-new"
C="$LAB/results/apple-extent-grid-contract-build-new"
python3 "$E/contracts.py" build --lab "$LAB" --archive "$A" --app-build "$O" \
  --old-shader "$S/apple.metallib" --old-manifest bridge/experiments/apple_application_icb/profiles.json --out "$C"
python3 "$E/contracts.py" run --lab "$LAB" --build "$C" --out "$LAB/results/apple-extent-grid-contract-new"
T="$LAB/results/apple-extent-grid-stage-build-new"
python3 bridge/experiments/standalone_inherited_pipeline/experiment.py build --lab "$LAB" --archive "$A" \
  --legacy "$STAGE/carrier.metallib" --shader "$STAGE/transform.metallib" \
  --wrong-shader "$STAGE/wrong-transform.metallib" --manifest "$STAGE/profiles.json" --out "$T"
for mode in direct auto; do python3 bridge/experiments/standalone_inherited_pipeline/experiment.py run --lab "$LAB" --build "$T" --mode "$mode" --out "$LAB/results/apple-extent-grid-stage-$mode-new"; done
python3 "$E/audit_original.py" --archive "$A" --sample "$S" --release "$APP" \
  --matrix "$LAB/results/apple-extent-grid-audit-new.json" --matrix-direct "$LAB/results/apple-extent-grid-direct-1-new" \
  --matrix-blank "$LAB/results/apple-extent-grid-blank-5-new" --original-build "$O" \
  --original-runs "$LAB/results/apple-original-extent-grid-1-new" "$LAB/results/apple-original-extent-grid-2-new" \
  --regression-build "$R" --regression "$LAB/results/apple-extent-grid-64-run-new" \
  --historical-direct '/path/to/archived-64-direct-run' --contract-build "$C" \
  --contract "$LAB/results/apple-extent-grid-contract-new" --stage-build "$T" \
  --stage-direct "$LAB/results/apple-extent-grid-stage-direct-new" --stage-auto "$LAB/results/apple-extent-grid-stage-auto-new" \
  --out "$LAB/results/apple-bounded-extents-audit-new.json"
```
