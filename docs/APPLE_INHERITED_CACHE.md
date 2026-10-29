# Scoped reuse of inherited Apple render records

For the exact registered Apple sample view profile, the scoped CPU render ICB
can now retain a previously materialized draw record when the inherited
pipeline object is unchanged. Before reuse, the adapter still validates the
current pipeline, pass, buffer bindings, ranges and formats. Changing a
command's pipeline, bindings, draw or reset invalidates its record. The reused
record and resources remain retained until the user command buffer completes.
Other inherited profiles keep their existing materialization path. This is a
process-local adapter change, not an installed driver or general ICB cache.

Two adapted processes each submit eight frames of 15 commands. Each starts with
15 materializations, reuses the cached commands, then changes the first mesh
binding on frame five and materializes that command again: **16 materializations
and 104 reuses per process**, versus 120 materializations without reuse. This
is an observed operation count, not a benchmark or demonstrated speedup.
The changed mesh and two alternating aspect values create four distinguishable
images. Direct and adapted captures match. Before installing the new mesh, a
16-byte vertex buffer is refused on the previously cached command without
committing the user command buffer; the valid mesh then succeeds.

The [auditor](apple-inherited-cache-validation.json) verifies two direct, two
adapted and two blank processes, 48 images, 147,456 pixels, 240 adapted packets,
16 invalid depth-store refusals and two short-buffer refusals. A separate
[regression](apple-cache-inherited-regression.json) validates three changes of
inherited pipeline on the previously qualified non-Apple profiles, with a
following direct draw. It does not test changing between two distinct pipeline
objects for the cached Apple profile. Reset, copying cached commands, thread
races and arbitrary shaders remain unqualified by this cohort. No timing or
performance gain is claimed. The Apple application is locally modified, the
original executable is not run, and transparent integration remains open.
All 83 pinned system-file hashes stayed unchanged.

## Reproduce

Prepare the pinned Apple assets as in [APPLE_CPU_ICB_GAP.md](APPLE_CPU_ICB_GAP.md),
and the separate non-Apple regression assets as in
[RENDER_INHERITED_SAME_ENCODER.md](RENDER_INHERITED_SAME_ENCODER.md). Use
fresh output directories and serialize GPU processes.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
VERTEX='/path/to/vertex_io_carrier.metallib'
PROFILE='/path/to/cpu_icb_vertex_profiles.json'
python3 tools/build_from_source.py --out build/apple-cache-new
A="$PWD/build/apple-cache-new"
E=bridge/experiments/apple_inherited_cache
B="$LAB/results/apple-cache-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-cache-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-cache-direct-1-new" "$LAB/results/apple-cache-auto-1-new" "$LAB/results/apple-cache-direct-2-new" "$LAB/results/apple-cache-auto-2-new" "$LAB/results/apple-cache-blank-1-new" "$LAB/results/apple-cache-blank-2-new" --out "$LAB/results/apple-cache-audit-new.json"
E=bridge/experiments/render_inherited_same_encoder
B="$LAB/results/apple-cache-regression-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$VERTEX" --manifest "$PROFILE" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-cache-regression-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --archive "$A" --runs "$LAB/results/apple-cache-regression-direct-1-new" "$LAB/results/apple-cache-regression-auto-1-new" "$LAB/results/apple-cache-regression-direct-2-new" "$LAB/results/apple-cache-regression-auto-2-new" --out "$LAB/results/apple-cache-regression-audit-new.json"
```
