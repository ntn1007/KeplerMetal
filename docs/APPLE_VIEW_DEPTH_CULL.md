# Depth comparison and face culling with the scoped Apple-shader ICB

This test uses the pinned Apple shader and the bounded 64×48 BGRA8/depth
profile from [the view-format experiment](APPLE_VIEW_ICB.md). It compares
ordinary direct draws with the scoped CPU ICB on the GTX 880M. Both paths use
the same registered pipeline, back-face culling and a `Depth32Float` attachment
cleared to 1. The shader emits depth 0.

Three cases discriminate the relevant state:

| Geometry | Depth comparison | Expected color target |
|---|---|---|
| Front-facing full-target triangle | `less` | Uniform shader color |
| Same triangle with reversed winding | `less` | Clear |
| Front-facing full-target triangle | `never` | Clear |

The two negative cases change winding and depth comparison separately. The
front-facing positive case proves the triangle and pipeline render in the
same setup. Depth writes are enabled, but these outputs do not independently
verify a later depth read or an occlusion ordering involving multiple draws.

## Evidence

Two direct/adapted pairs produced 12 completed GPU render buffers. The
[auditor](apple-view-depth-cull-validation.json) independently checks all
147,456 color bytes against CPU constants and 6,144 guard bytes. Direct and
adapted captures match exactly for each case. It also checks six adapted draw
packets, their retained native prefixes and resource/record metadata, along
with signed terminal processes, nonoverlapping reservations and selected
system-file hashes.

This demonstrates these specific culling and depth-comparison outcomes with
one command and one shader. It does not qualify arbitrary depth states,
multi-draw depth dependencies, overlapping frames, the original Apple app,
an MTKView drawable or transparent macOS integration. No performance
comparison was made and no installed driver was modified.

## Reproduce

Obtain the pinned Apple shader and legacy carrier as described in
[the sample analysis](APPLE_CPU_ICB_GAP.md). Use fresh output directories;
verify the terminal state of an uncertain process before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-depth-cull-new
A="$PWD/build/apple-depth-cull-new"
E=bridge/experiments/apple_view_depth_cull
B="$LAB/results/apple-depth-cull-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-depth-cull-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-depth-cull-direct-1-new" "$LAB/results/apple-depth-cull-auto-1-new" "$LAB/results/apple-depth-cull-direct-2-new" "$LAB/results/apple-depth-cull-auto-2-new" --out "$LAB/results/apple-depth-cull-audit-new.json"
```

The Apple library pin depends on the qualified local toolchain. Apple source,
its compiled library and vendor driver binaries are not redistributed here.
