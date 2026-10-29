# Framebuffer-only drawable with an independently read depth attachment

The 15-command Apple-shader ICB test now uses an unattached `CAMetalLayer`
with `framebufferOnly = YES`, the normal layer default. The client verifies
that the obtained drawable texture also reports `framebufferOnly = YES` and
uses it only as a color render attachment. In accordance with [Apple's texture
contract](https://developer.apple.com/documentation/metal/mtltexture/isframebufferonly),
it does not copy, sample or read that drawable texture.

Instead, the test enables depth writes, clears a separate `Depth32Float`
attachment to 1 and copies **that depth texture** into a shared buffer after
rendering. The pinned Apple shader writes depth 0. The test compares the
resulting depth images between direct draws and the scoped CPU ICB, and checks
expected object centers and background. An independent blank control runs the
same render pass with no draws; its entire depth image remains 1.

## GTX evidence

Two repetitions each of direct, adapted and blank modes completed 24 render
buffers: 16 with draws and eight blank controls. The
[auditor](apple-drawable-framebuffer-validation.json) checks 73,728 depth
floats, 12,288 guard bytes and 120 adapted draw packets. It checks that every
depth value is 0 or 1, verifies 15 expected centers per frame and a background
point, confirms direct/adapted depth images match and confirms the blank
images are all 1. This is not a full independent CPU rasterizer for every
pixel. The ICB contains 15 commands and is reused after a frame-state update;
shared and private frame-buffer variants match. A too-short object buffer at
the last slot is refused before submission.

All 24 presentation callbacks fired with `presentedTime = 0`; neither an
onscreen presentation nor the drawable's color pixels are proved by this
cohort. The layer was not attached to a window. The test confirms depth writes
associated with GPU draws in the same render pass, not that a person saw the
rendered color. It does not run the Apple application, validate overlapping
frames, compare performance or modify the system driver or OCLP. GPU reservation,
signed terminal processes and a bounded set of system-file hashes are audited.

## Reproduce

Obtain the pinned Apple shader and carrier as described in [the sample analysis](APPLE_CPU_ICB_GAP.md).
Use fresh output directories; establish terminal state before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-framebuffer-new
A="$PWD/build/apple-framebuffer-new"
E=bridge/experiments/apple_drawable_framebuffer
B="$LAB/results/apple-framebuffer-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-framebuffer-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-framebuffer-direct-1-new" "$LAB/results/apple-framebuffer-auto-1-new" "$LAB/results/apple-framebuffer-direct-2-new" "$LAB/results/apple-framebuffer-auto-2-new" "$LAB/results/apple-framebuffer-blank-1-new" "$LAB/results/apple-framebuffer-blank-2-new" --out "$LAB/results/apple-framebuffer-audit-new.json"
```

The shader hash depends on the qualified local compiler. Apple source, its
compiled library and vendor driver binaries are not redistributed here.
