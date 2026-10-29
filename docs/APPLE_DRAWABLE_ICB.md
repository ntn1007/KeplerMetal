# ICB rendering into an unattached CAMetalLayer drawable

The scoped Apple-shader CPU ICB now has a bounded test using a real
`CAMetalDrawable` texture obtained from a 64×48 BGRA8 `CAMetalLayer`. The layer
is not attached to a window. `framebufferOnly` is explicitly **false** so the
client can blit the texture into a CPU-readable buffer before requesting
presentation. This differs from a normal framebuffer-only drawable and does
not qualify the original Apple application's window or its default view.

The test retains the 15-command synthetic scene, depth attachment, back-face
cull state, inherited pipeline and two sequential frame-state generations.
It compares direct rendering with the process-local ICB. Shared frame buffers
and private frame buffers populated by an earlier same-command-buffer blit are
tested separately.

## GTX evidence and presentation limit

An initial native probe obtained a drawable, cleared it on the GPU and checked
its readback before scheduling `presentDrawable:`. Two direct/adapted ICB pairs
then completed 16 render buffers. The [auditor](apple-drawable-icb-validation.json)
compares 196,608 color bytes and 8,192 guard bytes, checks 240 expected object
centers and 120 adapted draw packets, and compares the images with a previously
recorded offscreen direct run. A short buffer in the final slot is refused
before submission in the adapted runs. The tests verify signed terminal
processes, nonoverlapping GPU reservations and selected system-file hashes.

All 16 drawable presentation callbacks fired, but every `presentedTime` was
zero. Apple documents that zero can mean the drawable was not presented or its
frame was dropped ([Apple documentation](https://developer.apple.com/documentation/metal/mtldrawable/presentedtime)).
Therefore these observations prove **GPU rendering and readback of the drawable
texture plus presentation requests**, not visible display. The callback alone
is not treated as proof that a frame appeared onscreen.

This test does not run the Apple app, use a window-attached drawable, enable
framebuffer-only mode, test overlapping frames or qualify transparent Metal
integration. There is no missing-blit control or performance comparison. The
system driver and OCLP were not modified.

A [subsequent framebuffer-only cohort](APPLE_FRAMEBUFFER_ONLY_ICB.md) checks
the same type of draw through a separate depth attachment; it still does not
establish visible presentation.

## Reproduce

Obtain the pinned shader and carrier as described in [the sample analysis](APPLE_CPU_ICB_GAP.md).
Use fresh output directories and establish terminal process state before any
retry. `OFFSCREEN` points to a previously recorded native offscreen reference.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
OFFSCREEN='/path/to/recorded-offscreen-direct-run'
python3 tools/build_from_source.py --out build/apple-drawable-new
A="$PWD/build/apple-drawable-new"
P=bridge/experiments/apple_drawable_probe
PB="$LAB/results/apple-drawable-probe-build-new"
PR="$LAB/results/apple-drawable-probe-new"
python3 "$P/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$P/profiles.json" --out "$PB"
python3 "$P/experiment.py" run --lab "$LAB" --build "$PB" --mode direct --out "$PR"
E=bridge/experiments/apple_drawable_icb
B="$LAB/results/apple-drawable-icb-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-drawable-icb-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --probe-build "$PB" --probe "$PR" --offscreen "$OFFSCREEN" --runs "$LAB/results/apple-drawable-icb-direct-1-new" "$LAB/results/apple-drawable-icb-auto-1-new" "$LAB/results/apple-drawable-icb-direct-2-new" "$LAB/results/apple-drawable-icb-auto-2-new" --out "$LAB/results/apple-drawable-icb-audit-new.json"
```

The library pin depends on the qualified local compiler. Apple source, its
compiled library and vendor drivers are not redistributed here.
