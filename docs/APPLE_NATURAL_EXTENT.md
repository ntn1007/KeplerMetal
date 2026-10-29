# Apple ICB at the sample's initial drawable extent

The scoped ICB path now accepts **800 × 600** as well as 64 × 48 for the
exact pinned Apple Release view shader and format. Two runs of the
unchanged-source Apple Release executable observed an initial 800 × 600
drawable and completed 15 adapted draws without the bootstrap resizing the
window. Both drawable captures match the instrumented direct-draw reference
byte for byte; the blank reference differs.

The app is still explicitly injected and its pipeline object is replaced by
the scoped one. Its original view was framebuffer-only; the test pauses the
view, changes that property to permit readback and adds a blit before present.
It does not prove visible presentation, unmodified runtime behavior, general
application compatibility or arbitrary window dimensions. Release assertions
are disabled and the device's reported family is not changed. The initial
extent is an observation on this display/session, not a guarantee for other
display configurations or scaling factors.

## What changed

The render engine now validates the current target **against the actual
pipeline**. All existing profiles retain their exact target constraints. The
new extent is allowed only for `apple_explicit_view`, the pinned Release
library and its existing BGRA8/depth profile. The 24-byte draw record is
materialized using the existing recording target; the native state prefix is
independently checked at the actual render extent before it is copied into
the uncommitted user command buffer. No arbitrary extent range is accepted.

## Evidence

The [natural-app audit](apple-natural-extent-validation.json) checks the two
original-executable captures, 17 source/project files against Apple's archive,
signed Mach-O sections, a 64 × 48 same-runtime regression, and a separate
non-Apple stage-in direct/ICB comparison with CPU-checked pixel regions.
Nine no-dispatch target controls accept only the two release-profile extents,
reject neighboring dimensions, a different format and 960 × 540, and confirm
the older shader profile still refuses 800 × 600.

The source-adapted Apple test has two separate six-process cohorts:

* [Fixed-size matrix](apple-native-extent-matrix.json): 48 frames at
  800 × 600, 240 adapted draw records, two aspect states and a mesh change.
  All direct and ICB images agree; blank images differ. The auditor checks
  23,040,000 pixels, 24,576 guard bytes and 3,686,400 row-padding bytes.
* [Extent transition matrix](apple-extent-transition-matrix.json): 48 frames
  alternate 64 × 48 and 800 × 600 in the same process, with the same ICB and
  a later mesh change. Direct and adapted outputs match, including when cached
  draw records are reused across the tested extent changes. The auditor
  checks 11,593,728 pixels, 24,576 guard bytes and 1,843,200 padding bytes.

Both cohorts include expected invalid-depth and short-binding refusals. The
cooperative reservation serializes participating laboratory processes, not
unrelated GPU clients. The system-file check is limited to the 83 pinned files;
no driver, OCLP or firmware modification, hardware video result or performance
claim is made.

## Reproduce

Obtain the sample, Release bundle, carrier and historical 64 × 48 direct
control as described in [APPLE_RELEASE_LIBRARY_ICB.md](APPLE_RELEASE_LIBRARY_ICB.md).
The stage-in build inputs are described in
[STANDALONE_INHERITED_PIPELINE.md](STANDALONE_INHERITED_PIPELINE.md).
All outputs must be fresh. Tests use the common GPU reservation and briefly
open windows in the graphical session; resolve an unknown child state before
retrying.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
APP='/path/to/Release/Indirect Command Buffers on CPU.app'
LOG='/path/to/apple-release-build.log'
CARRIER='/path/to/render_state_carrier.metallib'
DEFAULT="$APP/Contents/Resources/default.metallib"
STAGE='/path/to/previous-standalone-inherited-build'
python3 tools/build_from_source.py --out build/apple-extent-new
A="$PWD/build/apple-extent-new"
for tag in native_extent extent_transition; do
  E="bridge/experiments/apple_$tag"
  B="$LAB/results/$tag-build-new"
  python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" \
    --legacy "$CARRIER" --vertex "$DEFAULT" --manifest "$E/profiles.json" --out "$B"
  idx=0
  for mode in direct auto direct auto blank blank; do
    idx=$((idx + 1))
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" \
      --out "$LAB/results/$tag-$mode-$idx-new"
  done
  python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --vertex "$DEFAULT" \
    --runs "$LAB/results/$tag-direct-1-new" "$LAB/results/$tag-auto-2-new" \
           "$LAB/results/$tag-direct-3-new" "$LAB/results/$tag-auto-4-new" \
           "$LAB/results/$tag-blank-5-new" "$LAB/results/$tag-blank-6-new" \
    --out "$LAB/results/$tag-audit-new.json"
done
E=bridge/experiments/apple_original_native_extent
O="$LAB/results/apple-original-extent-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" \
  --release "$APP" --build-log "$LOG" --carrier "$CARRIER" --shader "$DEFAULT" \
  --profiles bridge/experiments/apple_release_library/profiles.json --out "$O"
for n in 1 2; do python3 "$E/experiment.py" run --lab "$LAB" --build "$O" --out "$LAB/results/apple-original-extent-$n-new"; done
R="$LAB/results/apple-extent-64-build-new"
python3 bridge/experiments/apple_release_library/experiment.py build --lab "$LAB" --archive "$A" \
  --sample "$S" --release "$APP" --build-log "$LOG" --carrier "$CARRIER" --shader "$DEFAULT" \
  --profiles bridge/experiments/apple_release_library/profiles.json --out "$R"
python3 bridge/experiments/apple_release_library/experiment.py run --lab "$LAB" --build "$R" --out "$LAB/results/apple-extent-64-run-new"
C="$LAB/results/apple-extent-contract-build-new"
python3 bridge/experiments/apple_native_extent/contracts.py build --lab "$LAB" --archive "$A" \
  --app-build "$O" --old-shader "$S/apple.metallib" \
  --old-manifest bridge/experiments/apple_application_icb/profiles.json --out "$C"
python3 bridge/experiments/apple_native_extent/contracts.py run --lab "$LAB" --build "$C" --out "$LAB/results/apple-extent-contract-new"
T="$LAB/results/apple-extent-stage-build-new"
python3 bridge/experiments/standalone_inherited_pipeline/experiment.py build --lab "$LAB" --archive "$A" \
  --legacy "$STAGE/carrier.metallib" --shader "$STAGE/transform.metallib" \
  --wrong-shader "$STAGE/wrong-transform.metallib" --manifest "$STAGE/profiles.json" --out "$T"
for mode in direct auto; do python3 bridge/experiments/standalone_inherited_pipeline/experiment.py run --lab "$LAB" --build "$T" --mode "$mode" --out "$LAB/results/apple-extent-stage-$mode-new"; done
python3 bridge/experiments/apple_native_extent/audit_original.py --archive "$A" --sample "$S" --release "$APP" \
  --matrix "$LAB/results/native_extent-audit-new.json" --matrix-direct "$LAB/results/native_extent-direct-1-new" \
  --matrix-blank "$LAB/results/native_extent-blank-5-new" --transition "$LAB/results/extent_transition-audit-new.json" \
  --original-build "$O" --original-runs "$LAB/results/apple-original-extent-1-new" "$LAB/results/apple-original-extent-2-new" \
  --regression-build "$R" --regression "$LAB/results/apple-extent-64-run-new" --historical-direct '/path/to/archived-64-direct-run' \
  --contract-build "$C" --contract "$LAB/results/apple-extent-contract-new" --stage-build "$T" \
  --stage-direct "$LAB/results/apple-extent-stage-direct-new" --stage-auto "$LAB/results/apple-extent-stage-auto-new" \
  --out "$LAB/results/apple-natural-extent-audit-new.json"
```
