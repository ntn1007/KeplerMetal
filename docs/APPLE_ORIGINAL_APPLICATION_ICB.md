# Unmodified Apple Release executable with local ICB adaptation

An Xcode Release build of Apple's CPU-encoded ICB sample, compiled from the
unchanged sample sources, ran twice on the GTX 880M with an explicitly
injected, process-local KeplerMetal bootstrap. Each run encoded the sample's
15 indirect draws and completed the command buffer containing those draws
and a GPU blit of its own drawable. Both 64 × 48 captures, including 512 guard
bytes, match a previously qualified direct-draw Apple sample reference byte
for byte and differ from its blank control.

This is an application-specific experiment, not transparent system support.
Release builds compile out the sample's assertions, including its Mac 2
family assertion. The bootstrap does **not** spoof the device family; a live
query still reports Mac 2 false. The sample's default library was loaded, but
the bootstrap substituted a certified pipeline compiled from a separately
generated library with the same sample shader source. These two libraries
have different hashes; their general equivalence is not established. Only this
captured image and the prior bounded shader-profile tests are compared.

The bootstrap checks the signed executable, the bundle's default library,
carrier, alternate shader, manifest, device and exact pipeline descriptor. It
creates one scope on one queue and changes no native shared class. The capture
temporarily extends a process-local queue/command-buffer class, sets the app's
own MTKView to a readable 64 × 48 drawable, and inserts a blit before the
sample's normal present. The process is therefore instrumented even though
its source and x86_64 executable sections are unchanged. The window was
visible according to AppKit; actual on-screen presentation is not proven.

## Evidence and boundaries

The [audit](apple-original-application-validation.json) verifies 17 source,
project and storyboard files against the independently obtained Apple archive;
all 16 file-backed x86_64 Mach-O sections in the ad-hoc signed executable
match the Xcode output. `NSApplicationMain` is imported and no KeplerMetal
symbol is imported by that executable. Signing changes the full binary and
its hash. The signed executable and separately signed bootstrap are retained
only in the local laboratory, not this repository.

Each run has a terminal cooperative GPU reservation, 15 recorded draw packets,
and a completed captured command buffer. The independent auditor compares
12,800 bytes per capture to the archived direct and blank controls, validates
the old controls against their historical audit, and checks the pinned system
files before and after. The first captured run predates the addition of the
frame hash to the runner's manifest; its frame is still checked byte for byte
against the independently pinned prior reference. A preliminary no-readback
run reached the same 15 draws but is not counted in the two image tests.

No uninstrumented original application, arbitrary shaders or Metal ICB
semantics, native system integration, hardware video, or performance gain is
established. The 83 tracked system-file hashes are a bounded non-regression
check, not a complete filesystem audit. No installed driver or OCLP change is
part of this experiment.

## Reproduce

Use the separately obtained sample and prerequisites in
[APPLE_CPU_ICB_GAP.md](APPLE_CPU_ICB_GAP.md) and
[APPLE_APPLICATION_ICB.md](APPLE_APPLICATION_ICB.md). The latter produces
the archived direct/blank controls for the exact sample and shader profile.
The Release configuration and its `NS_BLOCK_ASSERTIONS` setting must be
preserved. Xcode and its Metal toolchain are required. The application briefly
opens a window in the current graphical session.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
RELEASE="$LAB/results/apple-original-release-new"
xcodebuild -project "$S/source/Indirect Command Buffers on CPU.xcodeproj" \
  -scheme 'macOS - Indirect Command Buffers on CPU' -configuration Release \
  -derivedDataPath "$RELEASE" CODE_SIGNING_ALLOWED=NO build \
  > "$LAB/results/apple-original-release-build-new.log" 2>&1
python3 tools/build_from_source.py --out build/apple-original-new
E=bridge/experiments/apple_original_bootstrap
B="$LAB/results/apple-original-bootstrap-build-new"
APP="$RELEASE/Build/Products/Release/Indirect Command Buffers on CPU.app"
python3 "$E/experiment.py" build --lab "$LAB" --archive build/apple-original-new \
  --sample "$S" --release "$APP" \
  --build-log "$LAB/results/apple-original-release-build-new.log" \
  --carrier '/path/to/render_state_carrier.metallib' --shader "$S/apple.metallib" \
  --profiles bridge/experiments/apple_application_icb/profiles.json --out "$B"
for n in 1 2; do
  python3 "$E/experiment.py" run --lab "$LAB" --build "$B" \
    --out "$LAB/results/apple-original-bootstrap-run-$n-new"
done
python3 "$E/audit.py" --sample "$S" --release "$APP" --build "$B" \
  --direct '/path/to/archived-direct-run' --blank '/path/to/archived-blank-run' \
  --runs "$LAB/results/apple-original-bootstrap-run-1-new" \
         "$LAB/results/apple-original-bootstrap-run-2-new" \
  --out "$LAB/results/apple-original-bootstrap-audit-new.json"
```

The auditor pins historical direct/blank manifest hashes, so freshly generated
controls need an updated independently reviewed validation record rather than
silently inheriting the published one. Use fresh output paths; if a process's
terminal state is unknown, do not relaunch until it is resolved.
