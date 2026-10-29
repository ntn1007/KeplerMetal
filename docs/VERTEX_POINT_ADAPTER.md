# Certified point-write profile for the scoped CPU render ICB

The opt-in KeplerMetal CPU render ICB can now execute **one hash-certified
`void` vertex shader** that atomically writes to a shared buffer while drawing
points with rasterization disabled. The shader writes only four bytes at buffer
index 0, and bounds its vertex ID to five. The adapter accepts counts 0–5,
start 0, one instance and base instance 0. It checks the exact shader library
hash and manifest, reflected read/write ABI, bound device, shared storage,
16-byte offset alignment and at least four available bytes. It rechecks the
pipeline and resources at execution, declares read/write vertex resource usage,
and retains the record and resources through command-buffer completion.

The profile is deliberately tied to the exact locally built metallib and the
pinned NVIDIA driver ABI. It does **not** support arbitrary writable shaders,
point rendering in general, indexed draws, GPU-generated commands or transparent
system-wide Metal integration. Cross-queue ordering, concurrent use, private or
managed output buffers and arbitrary resource aliases remain unqualified. The
application must coordinate its own CPU/GPU accesses. A later [render-to-compute
qualification](VERTEX_POINT_DEPENDENCY.md) covers two same-queue arrangements
with device-created shared buffers. No performance claim is made.

## Validation

Two direct/adapted GTX process pairs produced identical raw buffer captures for
counts 0–5: 24 completed buffers and 3,072 intact guard bytes. The independent
[point audit](vertex-point-adapter-validation.json) checked those raw buffers,
the signed process and source hashes, the two shader/manifest identity
refusals per process, nine out-of-profile refusals per adapted process, and ten
copied native packets with their one-point primers. The refusals cover primitive,
count, start, instances, base instance, missing/short/private buffers and a
pipeline change. A count-zero command is skipped, rather than submitted.

Two additional direct/adapted pairs requalified the previous
[trailing-triangle profile](vertex-point-adapter-trailing-regression.json),
two pairs requalified the [legacy incomplete-triangle profile](vertex-point-adapter-partial-regression.json),
and two pairs requalified [explicit trailing geometry contracts](vertex-point-adapter-geometry-regression.json),
on the same runtime. These are bounded regression tests, not a complete graphics
conformance suite. All GTX processes were signed, terminal and serialized under
the shared GPU reservation. The specific system components checked by the
runners were unchanged. The runtime archive SHA-256 is
`d3b486058d77aa724c9a7374fe93ba10c35a9a4d3553dec0e58270b620b35981`.

## Reproduce

The [shader source](../bridge/experiments/vertex_point_adapter/point_write.metal)
is included; build with the same Metal toolchain/profile or the library hash
will not match. The local Apple/NVIDIA legacy carrier is not distributed. Use
fresh directories and establish a process's terminal state before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
LEGACY='/path/to/render_state_carrier.metallib'
E=bridge/experiments/vertex_point_adapter
S="$LAB/results/point-shader-new"
mkdir "$S"
xcrun -sdk macosx metal -std=macos-metal2.0 -c "$E/point_write.metal" -o "$S/point.air"
xcrun -sdk macosx metallib "$S/point.air" -o "$S/point.metallib"
shasum -a 256 "$S/point.metallib"
python3 tools/build_from_source.py --out build/point-adapter-new
A="$PWD/build/point-adapter-new"
B="$LAB/results/point-adapter-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/point.metallib" --manifest "$PWD/$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/point-adapter-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --archive "$A" --runs "$LAB/results/point-adapter-direct-1-new" "$LAB/results/point-adapter-auto-1-new" "$LAB/results/point-adapter-direct-2-new" "$LAB/results/point-adapter-auto-2-new" --out "$LAB/results/point-adapter-audit-new.json"
```
