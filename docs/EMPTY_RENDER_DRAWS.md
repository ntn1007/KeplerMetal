# Empty CPU-encoded render ICB commands

The process-local render adapter now accepts a triangle draw with zero
vertices or zero instances, or an indexed triangle draw with zero indices or
zero instances, **inside its existing descriptor, pipeline and geometry
profile**. The command clears any previously materialized record and is
represented as inert in the scoped command list. Reset still clears its state.
Nonzero commands use the existing transport. The normal index-buffer type,
device, offset and range checks remain in force even for empty indexed draws.
Incomplete triangles and unsupported primitive types are still refused.

This is a branch B extension of the project-owned, opt-in ICB implementation.
It does not modify the Apple/NVIDIA driver or make ICBs transparent to ordinary
applications. It does not qualify GPU-generated command records, arbitrary
pipelines, state mutation without reset, multiple queues or general Metal
semantics. The project currently treats an empty encoded draw like an inert
slot for execution and its internal range machinery; it does not claim that
all possible native ICB introspection or side effects are identical.

Apple describes the indirect draw as equivalent to the corresponding direct
draw: [indirect draw](https://developer.apple.com/documentation/metal/mtlindirectrendercommand/drawprimitives%28_%3Avertexstart%3Avertexcount%3Ainstancecount%3Abaseinstance%3A%29).
The documentation does not by itself establish every empty-command edge case;
the following tests bound the actual claim.

## Evidence

On the MacBook M1 Max, macOS 27.2 (26B118), SDK 27.0, the standalone
[public-Metal reference](../bridge/experiments/metal_empty_draw_reference/empty_draw.mm)
ran direct and native ICB draws. Each mode tested normal and zero-count/
zero-instance draws, with and without a 16-bit index buffer. Normal draws
produced 256 red pixels; empty draws produced 256 black pixels. Both command
buffers completed in each case. Source SHA-256 was
`6f610302224776827626da7bb4cb76cc579c95239d873480d45da867b23dbd72`;
the two JSON result hashes were
`d6075548440def70a2a74e274f27604f6eee04a0df68cf7a56685eb71ce81fe3`
and `c987a10f3b1593eb93b94708df1483b03cc7c0f2c09be5aceafa5fb42925f9d6`.
Those reference captures contain reported pixel counts, not raw images, and
do not qualify the NVIDIA GPU. [Summary validation](empty-render-m1-validation.json).

On the GTX 880M, two independent pairs of signed processes compared public
direct draws with the process-local adapted ICB path. Each process covered
seven cases, including a normal draw after reset. A separate offline audit
checks raw float images against an independent pixel oracle, compares direct
and adapted bytes, and verifies guards, process termination, signatures,
source hashes, scoped execution events and the installed profile. Across the
four processes, **344,064 float channels** and **14,336 guard bytes** matched;
the two adapted processes each refused three unsupported inputs.
[Sanitized audit](empty-render-validation.json).

The laboratory reservation serializes participating tests only. The runtime
archive is the one named in the audit; no qualification is inherited by a
different build. No performance benchmark or system replacement is claimed.
The historical render test's zero-vertex refusal has been replaced in the
current test with an incomplete-triangle refusal; its verifier still accepts
the old historical control so earlier captures are not reinterpreted.

## Reproduce on the qualified GTX host

Use the locally held, hash-pinned carrier metallib and fresh paths. The
original vendor components are not redistributed. Do not restart a test if
its process or reservation has not been observed terminal.

```bash
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
cd "$REPO"
python3 tools/build_from_source.py --out build/empty-render-new
ARCHIVE="$PWD/build/empty-render-new"
EXP=bridge/experiments/metal_empty_draw_reference
BUILD="$LAB/results/empty-render-build-new"
python3 "$EXP/experiment.py" build --out "$BUILD" --archive "$ARCHIVE" --carrier '/path/to/pinned/carrier.metallib'
for n in 1 2; do
  for mode in direct auto; do
    python3 "$EXP/experiment.py" run --lab "$LAB" --build "$BUILD" --out "$LAB/results/empty-render-$mode-$n-new" --mode "$mode"
  done
done
python3 "$EXP/audit.py" --build "$BUILD" --archive "$ARCHIVE" \
  --runs "$LAB/results/empty-render-direct-1-new" "$LAB/results/empty-render-auto-1-new" \
    "$LAB/results/empty-render-direct-2-new" "$LAB/results/empty-render-auto-2-new" \
  --out "$LAB/results/empty-render-audit-new.json"
```

The M1 reference can be rebuilt and run separately with `xcrun clang++
-std=c++17 -fobjc-arc empty_draw.mm -framework Metal -framework Foundation -o
empty_draw`, followed by `./empty_draw direct` and `./empty_draw icb` on an
appropriate Mac. It is an independent behavioral reference, not an iMac test.
