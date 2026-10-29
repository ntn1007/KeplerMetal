# Apple sample renderer with scoped ICB adaptation

A bounded host constructs `AAPLRenderer` from Apple's separately downloaded,
SHA-pinned CPU ICB sample. Its original gear-mesh creation, object placement,
frame update, private-buffer blit, and `drawInMTKView:` method run locally.
The host attaches an MTKView to a temporary non-key window and invokes two
frames. Apple's controller and original application UI do not run.

[adapt.py](../bridge/experiments/apple_real_renderer/adapt.py) verifies the
exact three Apple source hashes, then applies exact-match changes to a local
copy in the laboratory output directory. These changes opt in to the scoped
adapter for the sample shader and pipeline; direct mode replaces ICB execution
with equivalent direct draws, while blank mode emits no draws. All modes use
the same renderer and mesh generator. The harness makes the drawable readable
(`framebufferOnly = NO`), stores color and depth, copies only its own color
texture into a guarded buffer, and waits for each command buffer. The depth
store is required by the adapter's current pass validation. Apple sources,
compiled Apple artifacts and proprietary drivers are not in this repository.
This is a modified-process integration, not transparent driver integration.

## Results

Two direct, two adapted and two blank processes ran serially on the GTX 880M.
The independent [auditor](apple-real-renderer-validation.json) verifies all
12 captured frames, 36,864 pixels and 6,144 guard bytes. Every direct and
adapted image is byte-identical; blank images are uniform and differ from the
rendered images. One rendering contains 1,342 distinct BGRA pixel values.
The auditor checks 60 adapted draw packets with exact counts of 36 through 504
vertices across 15 meshes, three resource bindings per command, base instances,
private frame-state storage, asset hashes and terminal reservation records.

A preceding adapted attempt using MTKView's default depth store action was
refused with `Depth attachment outside qualified profile`; its user command
buffer was not committed. The subsequent change explicitly stores depth in all
three test modes. Two earlier builds failed at compilation and ran no GPU work.
These excluded attempts are preserved in the local lab.

The results demonstrate correct matching for this renderer and its particular
state, not complete ICB behavior, independent CPU rasterization, visible screen
presentation, the original UI, overlapping frames, or a benchmark. All 83
pinned system-file hashes remain unchanged; this is not a complete system audit.

## Reproduce

Prepare the pinned Apple archive, source and metallib according to
[APPLE_CPU_ICB_GAP.md](APPLE_CPU_ICB_GAP.md). The input files must match the
hashes embedded in the builder. A window is briefly shown. Run each process
serially under the existing shared GPU reservation and use new directories.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-real-new
A="$PWD/build/apple-real-new"
E=bridge/experiments/apple_real_renderer
B="$LAB/results/apple-real-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-real-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-real-direct-1-new" "$LAB/results/apple-real-auto-1-new" "$LAB/results/apple-real-direct-2-new" "$LAB/results/apple-real-auto-2-new" "$LAB/results/apple-real-blank-1-new" "$LAB/results/apple-real-blank-2-new" --out "$LAB/results/apple-real-audit-new.json"
```
