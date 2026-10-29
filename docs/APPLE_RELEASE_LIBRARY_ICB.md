# Apple Release library used directly by the scoped ICB experiment

The pinned Apple Release sample can now use **the bytes of its own bundle's
default Metal library** for the registered render pipeline. Two process-local
application runs each execute 15 indirect draws, complete a command buffer
containing a drawable readback, and reproduce the previously qualified direct
GTX image. The executable's x86_64 sections are unchanged by ad-hoc signing.

The pipeline is still a **separate object** constructed and returned by the
KeplerMetal scope. The bootstrap checks that the bundle's default library and
the registration snapshot are byte-identical; it does not claim object
identity or transparent system integration. The sample is built in Release,
where its Mac 2 assertion is disabled. A live query remains Mac 2 false. The
bootstrap is explicitly injected into this one process and adjusts its view
for capture. No system framework, driver, OCLP, or reported family is changed.

The common runtime's explicit-buffer allowlist adds only the exact Release
library SHA-256 and the exact `apple_explicit_view` descriptor. It continues
to accept both previously qualified profiles for the earlier library. Other
libraries, arbitrary shaders and untested descriptors are not accepted by
this extension.

## Evidence

The [application audit](apple-release-library-validation.json) checks two
serialized original-executable captures, a fresh old-library regression on the
same runtime, terminal reservations, source and executable identity, 15 draw
records per run, unchanged pinned system files and byte-for-byte equality to
the archived direct image; the archived blank image differs. A separate
no-dispatch registration client rejects six mutated profiles or hashes and a
duplicate, accepts the new view profile and old plain profile, and restores
the device class. Its scope may create Metal resources and pipelines; it does
not submit a GPU command buffer.

A second, deliberately **source-adapted** sample application provides the
[expanded matrix](apple-release-application-validation.json): six serialized
processes, 48 captured frames and 240 checked adapted draw records. Two
direct, two ICB and two blank processes cover two aspect states and a mesh
binding change; all direct/ICB captures match and blank captures differ. The
16 invalid depth-store and two short-buffer controls are refused before the
client command buffer is committed. The eight direct and blank frame hashes
also match the earlier separately compiled shader's archived images.

These are bounded functional comparisons, not a general proof that the two
compiled libraries are equivalent. The 83 system hashes are a bounded check;
no performance benchmark or hardware video execution was performed.

## Reproduce

Obtain the sample, carrier, Release bundle and direct/blank historical controls
as described in [APPLE_ORIGINAL_APPLICATION_ICB.md](APPLE_ORIGINAL_APPLICATION_ICB.md).
The commands below use fresh paths and the cooperative GPU reservation. The
tests briefly open sample windows in a graphical session. Keep runs serial and
resolve an unknown process state before any retry.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
APP='/path/to/Release/Indirect Command Buffers on CPU.app'
LOG='/path/to/apple-original-release-build.log'
CARRIER='/path/to/render_state_carrier.metallib'
DEFAULT="$APP/Contents/Resources/default.metallib"
E=bridge/experiments/apple_release_library
A="$PWD/build/apple-release-library-new"
B="$LAB/results/apple-release-library-build-new"
R="$LAB/results/apple-release-regression-build-new"
C="$LAB/results/apple-release-contract-build-new"
python3 tools/build_from_source.py --out "$A"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" \
  --release "$APP" --build-log "$LOG" --carrier "$CARRIER" --shader "$DEFAULT" \
  --profiles "$E/profiles.json" --out "$B"
python3 bridge/experiments/apple_original_bootstrap/experiment.py build \
  --lab "$LAB" --archive "$A" --sample "$S" --release "$APP" --build-log "$LOG" \
  --carrier "$CARRIER" --shader "$S/apple.metallib" \
  --profiles bridge/experiments/apple_application_icb/profiles.json --out "$R"
python3 "$E/contracts.py" build --lab "$LAB" --archive "$A" --app-build "$B" \
  --old-shader "$S/apple.metallib" --out "$C"
python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --out "$LAB/results/release-run-1-new"
python3 bridge/experiments/apple_original_bootstrap/experiment.py run --lab "$LAB" \
  --build "$R" --out "$LAB/results/release-regression-new"
python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --out "$LAB/results/release-run-2-new"
python3 "$E/contracts.py" run --lab "$LAB" --build "$C" --out "$LAB/results/release-contract-new"
python3 "$E/audit.py" --sample "$S" --release "$APP" --archive "$A" --build "$B" \
  --regression-build "$R" --regression "$LAB/results/release-regression-new" \
  --contract-build "$C" --contract "$LAB/results/release-contract-new" \
  --direct '/path/to/archived-direct-run' --blank '/path/to/archived-blank-run' \
  --runs "$LAB/results/release-run-1-new" "$LAB/results/release-run-2-new" \
  --out "$LAB/results/release-audit-new.json"
```

The historical-control manifests are pinned to the published prior audit.
Newly generated controls require their own independently reviewed validation
record. To reproduce the expanded matrix:

```sh
E=bridge/experiments/apple_release_application
M="$LAB/results/apple-release-matrix-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" \
  --legacy "$CARRIER" --vertex "$DEFAULT" --manifest "$E/profiles.json" --out "$M"
idx=0
for mode in direct auto direct auto blank blank; do
  idx=$((idx + 1))
  python3 "$E/experiment.py" run --lab "$LAB" --build "$M" --mode "$mode" \
    --out "$LAB/results/release-matrix-$mode-$idx-new"
done
python3 "$E/audit.py" --sample "$S" --build "$M" --archive "$A" --vertex "$DEFAULT" \
  --runs "$LAB/results/release-matrix-direct-1-new" "$LAB/results/release-matrix-auto-2-new" \
         "$LAB/results/release-matrix-direct-3-new" "$LAB/results/release-matrix-auto-4-new" \
         "$LAB/results/release-matrix-blank-5-new" "$LAB/results/release-matrix-blank-6-new" \
  --out "$LAB/results/release-matrix-audit-new.json"
```
