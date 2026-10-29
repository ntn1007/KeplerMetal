# Local Apple sample application with scoped ICB adaptation

A locally built, instrumented copy of the Apple CPU ICB sample now runs as a
macOS application bundle. Its executable calls `NSApplicationMain`, loads the
sample storyboard and reaches the sample controller's `viewDidAppear`. The
local test then requests eight frames, checks its own drawable pixels and
terminates the app. All six audited windows were reported visible by AppKit
and non-key. This is the Apple sample's application lifecycle with modified
source and a test harness, **not** the original unmodified executable.

The local build starts from the separately obtained sample and its Xcode-built
bundle. It verifies the source hashes, recompiles the original storyboard and
compiles local copies of the renderer, controller and entry point. Those copies
explicitly install KeplerMetal's scope and registered pipeline, bypass the
sample's Mac-family assertion without changing the device's reported family,
use a readable 64 × 48 drawable and bound/terminate the run. The renderer's
ordinary public Metal render-encoder call is retained. The GPU, system driver,
frameworks and OCLP are not replaced. Apple sources and compiled artifacts
remain outside the public repository.

The host executable is ad-hoc signed before copying it into the local bundle;
the complete bundle is **not** code-signed as a unit. Before each process, the
runner verifies the signature of an identical standalone executable and hashes
all bundle files, rejecting symlinks; the auditor verifies those hashes again.
Three preliminary signing attempts on the copied bundle or its executable
failed with Finder-metadata errors; none dispatched GPU work. A preliminary
six-process cohort before the symlink restriction is preserved and excluded.

## Evidence and limits

Two direct, two scoped-ICB and two blank app processes ran serially under the
shared GPU reservation. The [auditor](apple-application-icb-validation.json)
checks the `NSApplicationMain` import, application bundle, source and executable
hashes, process termination, 48 frames, 147,456 pixels, 24,576 guard bytes and
240 adapted draw packets. Direct and adapted images match across two aspect
states and a mesh change; blank images are uniform. Two short-buffer and 16
invalid depth-store controls are refused before user command-buffer commit.
Each adapted process reports eight ordinary client encoder creations, 16
internal recording encoders, 16 materializations and 104 cached reuses. The
queue's original class is restored and three NVIDIA class-method IMPs stay
unchanged. All 83 pinned system-file hashes remain unchanged.

The comparison uses instrumented captures of the app's own drawable, not a
screen capture; actual visible presentation is not proved. The sample's
unmodified executable, arbitrary applications, complete ICB behavior, GPU
parallelism and transparent integration are also unproved. No performance
benchmark is claimed for this experiment.

## Reproduce

Use the exact local Apple archive, source, Xcode-built sample bundle and
metallib produced by [APPLE_CPU_ICB_GAP.md](APPLE_CPU_ICB_GAP.md), plus the
legacy carrier. A graphical session and the matching x86_64 toolchain are
required. The test briefly opens an instrumented window. Use fresh outputs
and run GPU processes serially.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-application-new
A="$PWD/build/apple-application-new"
E=bridge/experiments/apple_application_icb
B="$LAB/results/apple-application-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-application-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-application-direct-1-new" "$LAB/results/apple-application-auto-1-new" "$LAB/results/apple-application-direct-2-new" "$LAB/results/apple-application-auto-2-new" "$LAB/results/apple-application-blank-1-new" "$LAB/results/apple-application-blank-2-new" --out "$LAB/results/apple-application-audit-new.json"
```
