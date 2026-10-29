# Four- and five-vertex triangles in the scoped CPU render ICB

The project-owned CPU render ICB accepts non-indexed triangle draws of four or
five vertices for registered nonlegacy stage-in pipelines. It preserves the
requested vertex count in the native command record, and validates buffer bounds
through the last requested vertex. The existing declared-geometry checks and
execution-time checks remain in effect. Counts one and two remain restricted to
the separately qualified legacy inert path; count seven and legacy counts four
or five remain refused. Indexed behavior is unchanged.

This is an **opt-in, application-local** extension, not a system-driver change
or transparent Metal support. The GPU experiment uses one pinned `smooth`
vertex/fragment profile, one instance, vertex start 1 and a side-effect-free
shader. It does not qualify arbitrary shaders, resources, geometry, bindings,
other primitive types, or concurrent use. No performance claim is made.

## Evidence and limits

- On the GTX 880M, two direct/adapted pairs rendered counts 3, 4 and 5 in 12
  completed buffers. The independent auditor checked 147,456 float channels and
  6,144 guard bytes; direct and adapted raw images matched. It decoded the
  adapted command packets and checked the requested counts. Pixel results and
  command bytes do **not** prove that trailing vertices were invoked by the GPU.
- Ten expected adapted-path refusals cover nonlegacy counts 1, 2 and 7, legacy
  count 4 and a too-short vertex buffer at execution. A pre-change direct
  baseline rendered counts 3/4/5 and the old adapter refused count 4.
- Separate repeated GTX regressions on the same archive cover the earlier
  incomplete-triangle and zero-draw paths: 688,128 float channels and 28,672
  guard bytes. A state-change regression checks six refusals and eight
  completed render buffers. The signed GPU processes were terminal and
  nonoverlapping under the cooperative reservation.
- A public Metal reference on the M1 Max compared direct and native ICB draws
  for non-indexed and indexed counts 3/4/5. All 12 reported cases completed
  with the expected pixel counts. Raw M1 pixels were not retained, and this is
  not a GTX execution test. Indexed cases are **reference only** and do not
  extend indexed behavior on the iMac.

[GTX audit](render-trailing-vertices-validation.json),
[incomplete regression](render-trailing-partial-regression.json),
[zero regression](render-trailing-zero-regression.json),
[state regression](render-trailing-state-regression.json), and
[M1 audit](render-trailing-vertices-m1-validation.json) contain captured hashes.
The GTX runtime archive SHA-256 is
`c8dae5ab3c4a40dff7db0f69a2020198d98092ae9cea05993abe8b35a1a92a5c`.
System components checked by the runners were unchanged; this is not a complete
proof about every system file. No system driver, OCLP or firmware was modified.

## Reproduce

Use fresh output directories and the exact locally supplied, hash-pinned carrier
assets; proprietary assets are not distributed. The auditor additionally needs
the recorded old build and old direct/adapted baseline captures. Those records
are not recreated by the following commands. Never retry a process until its
terminal state is known.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
LEGACY='/path/to/render_state_carrier.metallib'
VERTEX='/path/to/vertex_io_carrier.metallib'
PROFILE='/path/to/cpu_icb_vertex_profiles.json'
OLD_BUILD='/path/to/recorded-old-build'
OLD_DIRECT='/path/to/recorded-old-direct'
OLD_AUTO='/path/to/recorded-old-auto'
python3 tools/build_from_source.py --out build/trailing-new
A="$PWD/build/trailing-new"
E=bridge/experiments/render_trailing_vertices
B="$LAB/results/trailing-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$VERTEX" --manifest "$PROFILE" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/trailing-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --archive "$A" --baseline-build "$OLD_BUILD" --baseline-direct "$OLD_DIRECT" --baseline-auto "$OLD_AUTO" --runs "$LAB/results/trailing-direct-1-new" "$LAB/results/trailing-auto-1-new" "$LAB/results/trailing-direct-2-new" "$LAB/results/trailing-auto-2-new" --out "$LAB/results/trailing-audit-new.json"
```

The [M1 reference](../bridge/experiments/render_trailing_vertices/reference.mm)
uses public Metal calls. Compile with `xcrun clang++ -std=c++17 -fobjc-arc
reference.mm -framework Metal -framework Foundation -o reference` and run
`reference direct` and `reference icb`. The accompanying auditor is pinned to
the recorded captures; new runs need a separately reviewed profile.
