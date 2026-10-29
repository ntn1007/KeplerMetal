# Window-attached framebuffer-only ICB depth witness

The previous framebuffer-only test used an unattached layer. This test attaches
an equivalent `CAMetalLayer` to a temporary 64 × 48 borderless `NSWindow`,
orders it front without activating the app, ignores mouse events, and pumps the
run loop. Each process verifies that the window is visible according to AppKit,
that it is not the key window, and that the view contains the tested layer. The
window is closed by a C++ scope guard. The render target remains
`framebufferOnly`; its color is never sampled or read back. A separate depth
attachment supplies the GPU witness. The exact Apple shader and carrier are
local dependencies, not distributed here.

## Results and limits

Two direct, two scoped adapted ICB and two no-draw control processes completed
serially under the shared GPU reservation. The [auditor](apple-window-icb-validation.json)
checks 24 render buffers, 120 adapted draw packets, 73,728 depth floats and
12,288 guard bytes. Adapted and direct depth outputs match for both frame
states and shared/private frame buffers. Every blank image is depth 1 and two
short-buffer controls are refused before submission. The check covers expected
centers and all depth values, not an independent rasterization of all pixels.

All 24 presentation callbacks fired, but all `presentedTime` values were zero.
AppKit's `isVisible` and the callback do not independently establish visible
pixels. The display state, occlusion, compositor and timestamp support were not
isolated; the cause is unknown. No screen capture, color readback, original
Apple application, overlapping frames, transparent integration or benchmark was
used. This demonstrates GPU depth writes with an attached layer, not visible
presentation or a general ICB implementation. The 83 pinned system files were
unchanged; this is not a complete audit of all system files.

## Reproduce

Prepare the pinned sample library and render-state carrier as in
[the sample analysis](APPLE_CPU_ICB_GAP.md). Use fresh output directories and
verify each process has terminated before beginning another run.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-window-new
A="$PWD/build/apple-window-new"
E=bridge/experiments/apple_window_icb
B="$LAB/results/apple-window-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-window-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-window-direct-1-new" "$LAB/results/apple-window-auto-1-new" "$LAB/results/apple-window-direct-2-new" "$LAB/results/apple-window-auto-2-new" "$LAB/results/apple-window-blank-1-new" "$LAB/results/apple-window-blank-2-new" --out "$LAB/results/apple-window-audit-new.json"
```

The test opens a small visible window. It requires an active graphical session
and the qualified x86_64 toolchain, system files and assets pinned by the runner.
