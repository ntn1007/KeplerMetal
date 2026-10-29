# Incomplete triangles in the scoped CPU render ICB

The project-owned CPU render ICB now accepts triangle draws with **one or two
vertices or indices** for its exact, pinned legacy `vs_state` / `fs_state`
pipeline. In this limited profile the command is treated as inert: it clears
any previously materialized record and contributes no GPU draw. Reset still
clears the command. A complete three-vertex draw still uses the existing native
transport.

This is safe only within the qualified profile: the pinned vertex shader has no
buffer bindings or observable writes, and one or two vertices cannot form a
triangle. The implementation requires that legacy pipeline when the incomplete
command is encoded, restricts start/base/instance values, preserves index type,
device and bounds checks, and rechecks the pipeline and bindings before
execution. The recheck matters because command state can change after encoding.
It must not be generalized to shaders with side effects: omitting their vertex
invocations could change application results. A later [state-guard test](PARTIAL_TRIANGLE_STATE_GUARD.md) exercises a changed
registered pipeline and vertex binding, plus restoration and copying; its
coverage remains bounded.

This is an **opt-in application-local** extension, not a system driver update
or transparent Metal support. Non-legacy incomplete draws and three-plus counts with a remainder remain
unqualified except for the separately tested [four/five-vertex stage-in profile](RENDER_TRAILING_VERTICES.md). Other primitive types, GPU-generated ICBs, arbitrary resources and
all indirect-command-buffer introspection remain unqualified. No performance
claim is made.

## Validation

- On the iMac GTX 880M, two direct/adapted process pairs cover seven cases each:
  complete, one and two vertices; complete, one and two 16-bit indices; and a
  complete draw after reset. The independent auditor checks **344,064 float
  channels and 14,336 guard bytes**, and the four sets of raw images match.
  The adapted path skips the four incomplete draws rather than submitting them;
  the completed render passes and readback verify the resulting pixels, not
  execution of those omitted draws. Fourteen API refusals cover wrong primitive,
  four vertices, invalid index alignment, no pipeline, start, instance count
  and indexed base outside this profile.
- A separate four-process direct/adapted regression on the **same runtime
  archive** checks the prior zero-count/zero-instance behavior, another 344,064
  float channels and 14,336 guard bytes. Earlier unrelated GPU cohorts have not
  been requalified on this archive.
- The MacBook M1 Max public-Metal reference compares direct with native ICB
  draws for six matching cases: incomplete draws produce 256 black pixels and
  complete draws 256 red pixels. The saved reference records counts rather than
  raw pixel buffers. It is a behavior comparison, not an NVIDIA GPU test.

[GTX audit](partial-triangle-validation.json), [zero-draw regression](partial-triangle-zero-regression-validation.json)
and [M1 audit](partial-triangle-m1-validation.json) contain the qualified hashes.
The GTX archive SHA-256 is
`21b32ca58d2f5bca072721ff7c71f03855cd9e2587465bda7a3c55869bb81eb9`.
All participating GTX processes were signed, terminal and nonoverlapping under
the cooperative lab reservation. The system profile checked by the runners was
unchanged. No system, OCLP or firmware modification was made.

## Reproduce

Use the exact pinned local carrier and fresh output directories. Build and run
from the repository root; the shared host reservation serializes participating
GPU clients. If a process is not known to be terminal, inspect it before retry.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
CARRIER='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/partial-triangle-new
A="$PWD/build/partial-triangle-new"
for exp in metal_partial_triangle_reference metal_partial_triangle_zero_regression; do
  E="bridge/experiments/$exp"
  B="$LAB/results/$exp-build-new"
  python3 "$E/experiment.py" build --out "$B" --archive "$A" --carrier "$CARRIER"
  for n in 1 2; do
    for mode in direct auto; do
      python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --out "$LAB/results/$exp-$mode-$n-new" --mode "$mode"
    done
  done
  python3 "$E/audit.py" --build "$B" --archive "$A" --runs "$LAB/results/$exp-direct-1-new" "$LAB/results/$exp-auto-1-new" "$LAB/results/$exp-direct-2-new" "$LAB/results/$exp-auto-2-new" --out "$LAB/results/$exp-audit-new.json"
done
```

The M1 source is [reference.mm](../bridge/experiments/metal_partial_triangle_reference/reference.mm).
Build it with `xcrun clang++ -std=c++17 -fobjc-arc reference.mm -framework Metal
-framework Foundation -o reference` and run `reference direct` and `reference icb`
on an appropriate reference Mac. The [M1 auditor](../bridge/experiments/metal_partial_triangle_reference/audit_m1.py)
is pinned to the recorded run and requires a new profile for new captures.
