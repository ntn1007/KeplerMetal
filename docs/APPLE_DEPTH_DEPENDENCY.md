# Depth dependency between two Apple-shader ICB draws

The scoped CPU ICB executes two overlapping triangles using the exact Apple
sample shader, a 64×48 BGRA8 target and a `Depth32Float` attachment. Both
triangles produce depth 0 and use `less` comparison; their vertex buffers
give them different, constant colors. The direct path performs equivalent
ordinary draws. The cases differ only in depth write enablement or clear value:

| Depth write | Clear depth | Observed color |
|---|---:|---|
| Enabled | 1 | First triangle |
| Disabled | 1 | Second triangle |
| Enabled | 0 | Clear; neither passes `less` |

With writes enabled, the first passing draw leaves depth 0 and the second
equal-depth draw is rejected. Without writes, both pass and the second color
replaces the first. The clear-zero case checks that the initial depth affects
both draws. These are conclusions for this controlled sequence; no depth
texture is read back by the CPU.

## GTX evidence

Two direct/adapted pairs completed 12 render buffers. The
[auditor](apple-depth-dependency-validation.json) independently checks
147,456 color bytes and 6,144 guard bytes against the three CPU expectations.
Direct and adapted raw captures match. Twelve adapted draw packets, their
retained state prefixes and resource identities are checked, together with
signed terminal processes, nonoverlapping reservations and selected
system-file hashes.

This extends the earlier [single-draw depth and cull controls](APPLE_VIEW_DEPTH_CULL.md).
It does not qualify arbitrary depth formats, distinct geometric depths,
cross-command-buffer dependencies, overlapping frames, the original Apple
application or transparent system integration. The test does not benchmark
performance or alter installed drivers.

## Reproduce

Obtain the pinned shader and legacy carrier as described in
[the sample analysis](APPLE_CPU_ICB_GAP.md). Use fresh outputs and establish
the terminal state of an uncertain process before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-depth-dependency-new
A="$PWD/build/apple-depth-dependency-new"
E=bridge/experiments/apple_depth_dependency
B="$LAB/results/apple-depth-dependency-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-depth-dependency-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-depth-dependency-direct-1-new" "$LAB/results/apple-depth-dependency-auto-1-new" "$LAB/results/apple-depth-dependency-direct-2-new" "$LAB/results/apple-depth-dependency-auto-2-new" --out "$LAB/results/apple-depth-dependency-audit-new.json"
```

The pinned Apple metallib depends on the qualified local toolchain. Apple
source, its compiled library and vendor drivers are not redistributed here.
