# MTKView framebuffer-only ICB depth witness

This test uses an actual `MTKView` in a temporary non-key, borderless 64 × 48
window. The view is paused and explicitly receives `draw`; a delegate performs
one render inside each `drawInMTKView:` call. Each frame uses the view's
`currentRenderPassDescriptor`, `currentDrawable`, and `depthStencilTexture`;
the client checks the descriptor and drawable share the same framebuffer-only
color texture and the depth texture has the expected size and format. Color
is never sampled or read back. The app closes its window on normal and exception
exits. The pinned Apple shader and carrier are local dependencies and are not
distributed here.

## Results and limits

Two direct, two scoped adapted ICB and two no-draw control processes completed
serially under the shared GPU reservation. The [auditor](apple-mtkview-icb-validation.json)
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
used. This demonstrates GPU depth writes through MTKView with an attached layer, not visible
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
python3 tools/build_from_source.py --out build/apple-mtkview-new
A="$PWD/build/apple-mtkview-new"
E=bridge/experiments/apple_mtkview_icb
B="$LAB/results/apple-mtkview-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-mtkview-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-mtkview-direct-1-new" "$LAB/results/apple-mtkview-auto-1-new" "$LAB/results/apple-mtkview-direct-2-new" "$LAB/results/apple-mtkview-auto-2-new" "$LAB/results/apple-mtkview-blank-1-new" "$LAB/results/apple-mtkview-blank-2-new" --out "$LAB/results/apple-mtkview-audit-new.json"
```

The test opens a small visible window. It requires an active graphical session
and the qualified x86_64 toolchain, system files and assets pinned by the runner.
