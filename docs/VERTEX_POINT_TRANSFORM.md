# Certified two-buffer point transform

The scoped CPU render ICB can now execute a second hash-certified `void` vertex
shader with rasterization disabled. It reads one `uint32` per point from a
shared source buffer and atomically stores `source[i] * 3 + 7` modulo 2³² into
a shared destination buffer. Draws are non-indexed points, with start 0, one
instance, base instance 0 and a count from 0 through 256. Count zero is skipped.
The atomic store avoids relying on an assumption that a vertex ID is never
executed more than once.

The adapter pins the exact shader library and manifest, checks the reflected
read-only source and read/write destination ABI, and requires two same-device
shared buffer objects. It validates each bound range for `count * 4` bytes at a
16-byte-aligned offset before execution; binding the **same buffer object** in
both slots is refused. Different buffer objects can still refer to overlapping
physical memory: the caller must ensure that input and output do not alias.
The adapter declares vertex read usage for the source and read/write usage for
the destination, revalidates state at execution, and retains records/resources
through completion.

This is an opt-in, application-local profile for one shader and a pinned NVIDIA
stack. It does not implement arbitrary vertex shaders, GPU-generated ICBs,
indexed draws, arbitrary storage modes, concurrent use or transparent Metal
support. Cross-queue ordering and aliasing across distinct objects are not
qualified. The application remains responsible for CPU/GPU synchronization.
A [public-Metal-only test client](STANDALONE_POINT_TRANSFORM.md) later used this
profile through explicit process-local opt-in. No speed claim is made.

## Validation

Two native reference processes and two direct/adapted process pairs ran on the
GTX 880M. The pairs tested counts 0, 1, 17, 128 and 256; the native reference
covered 0, 1, 17 and 256. The independent [audit](vertex-point-transform-validation.json)
compared all 10,240 captured input/output words from the pairs with a CPU
oracle, verified 5,120 guard bytes, and checked eight native ICB packets. The
native reference added 4,096 checked words and 2,048 guard bytes, and matched
the common direct/adapted cases. Each adapted process rejected 14 invalid cases,
including bounds, missing/private resources, the same object in both slots,
wrong geometry and pipeline change. Shader and manifest identity controls were
refused in all four paired processes.

Separate repeated GTX cohorts on the same archive passed the prior
[atomic point profile](vertex-point-transform-point-regression.json),
[trailing-triangle profile](vertex-point-transform-trailing-regression.json),
and [legacy incomplete-triangle profile](vertex-point-transform-partial-regression.json).
They are bounded regressions, not a complete graphics conformance test. All
GPU clients were signed, terminal and serialized through the cooperative lab
reservation. The checked system components were unchanged. The runtime archive
SHA-256 is `9c5edae4c0bf28878d2a808e117c21472a455ff5236048f88f2f9ed9b3ad22e3`.

## Reproduce

The [shader source](../bridge/experiments/vertex_point_transform/transform.metal)
is included. The exact metallib hash depends on the Metal toolchain; the
profile rejects a different hash. Obtain the legacy carrier locally, as it is
not distributed. Use fresh output directories and determine that a GPU process
is terminal before retrying. The auditor also requires two native-reference
captures produced by `native/experiment.py`.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
LEGACY='/path/to/render_state_carrier.metallib'
E=bridge/experiments/vertex_point_transform
S="$LAB/results/transform-shader-new"
mkdir "$S"
xcrun -sdk macosx metal -std=macos-metal2.0 -c "$E/transform.metal" -o "$S/transform.air"
xcrun -sdk macosx metallib "$S/transform.air" -o "$S/transform.metallib"
shasum -a 256 "$S/transform.metallib"
N="$LAB/results/transform-native-build-new"
python3 "$E/native/experiment.py" build --lab "$LAB" --shader "$S/transform.metallib" --out "$N"
for n in 1 2; do python3 "$E/native/experiment.py" run --lab "$LAB" --build "$N" --out "$LAB/results/transform-native-$n-new"; done
python3 tools/build_from_source.py --out build/transform-new
A="$PWD/build/transform-new"
B="$LAB/results/transform-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/transform.metallib" --manifest "$PWD/$E/profiles.json" --out "$B"
for n in 1 2; do for mode in direct auto; do python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/transform-$mode-$n-new"; done; done
python3 "$E/audit.py" --build "$B" --archive "$A" --native-build "$N" --native-runs "$LAB/results/transform-native-1-new" "$LAB/results/transform-native-2-new" --runs "$LAB/results/transform-direct-1-new" "$LAB/results/transform-auto-1-new" "$LAB/results/transform-direct-2-new" "$LAB/results/transform-auto-2-new" --out "$LAB/results/transform-audit-new.json"
```
