# Depth `DontCare` in the scoped render adapter

The scoped render-pass validator now accepts `MTLStoreActionDontCare` as well
as `Store` for the depth attachment, while preserving all existing device,
format, dimensions, clear-load, finite-clear-value and stencil checks. The
native pass descriptor is not rewritten. This does not promise depth contents
after the render pass; `DontCare` explicitly permits discarding them. Other
store actions remain refused. This is process-local adapter behavior, not a
system driver update or complete Metal feature support.

The previous [Apple renderer test](APPLE_REAL_RENDERER.md) had to override
MTKView's default depth store. A new separately adapted copy leaves that action
untouched and asserts the actual value is `DontCare`. Across two direct, two
adapted and two blank processes, [the auditor](apple-depth-dontcare-validation.json)
verifies 12 frames, 36,864 pixels, 60 adapted draw packets and 6,144 guard
bytes. Adapted and direct images are identical and differ from the uniform
blank. Four invalid multisample-resolve store actions are refused by the
adapter before the user command buffer is committed. The Apple controller and
original UI are not run; the harness still opts into the adapter and color
readback. No visible presentation or performance improvement is claimed.

A second [audited cohort](apple-depth-dontcare-dependency-validation.json)
uses two overlapping draws with `DontCare`. With depth writes enabled the
first draw wins; with writes disabled the second wins; clearing depth to zero
rejects both. Direct and adapted colors agree for 12 render buffers and 147,456
color bytes. The depth texture is never read after the pass. The same three
cases using `Store` pass a separate [regression cohort](apple-depth-store-regression-validation.json)
on the same rebuilt archive. These tests exercise the named shader, pipeline,
formats and state; other shaders and pass configurations are not individually
qualified. All 83 pinned system-file hashes remained unchanged.

## Reproduce

First obtain the exact local Apple assets described in [APPLE_CPU_ICB_GAP.md](APPLE_CPU_ICB_GAP.md).
Commands below create new outputs and serialize every GPU process. The first
cohort opens a small window; the others render offscreen.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/depth-dontcare-new
A="$PWD/build/depth-dontcare-new"
E=bridge/experiments/apple_depth_dontcare
B="$LAB/results/depth-dontcare-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/depth-dontcare-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/depth-dontcare-direct-1-new" "$LAB/results/depth-dontcare-auto-1-new" "$LAB/results/depth-dontcare-direct-2-new" "$LAB/results/depth-dontcare-auto-2-new" "$LAB/results/depth-dontcare-blank-1-new" "$LAB/results/depth-dontcare-blank-2-new" --out "$LAB/results/depth-dontcare-audit-new.json"

for kind in apple_depth_dontcare_dependency apple_depth_dependency; do
  E="bridge/experiments/$kind"
  B="$LAB/results/$kind-build-new"
  python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
  for n in 1 2; do
    for mode in direct auto; do
      python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/$kind-$mode-$n-new"
    done
  done
  python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/$kind-direct-1-new" "$LAB/results/$kind-auto-1-new" "$LAB/results/$kind-direct-2-new" "$LAB/results/$kind-auto-2-new" --out "$LAB/results/$kind-audit-new.json"
done
```
