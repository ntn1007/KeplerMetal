# Scoped CPU ICBs for the Apple sample's explicit buffers

The process-local CPU render ICB now accepts an **exact, hash-pinned** build of
the Apple CPU ICB sample shader and the accompanying project manifest. The
registered profile verifies three active read-only vertex arguments, including
their reflected names, sizes and alignments. Before encoding a draw, it checks
the actual vertex range, object index and frame-state buffer extent and
alignment; the tested profile admits complete non-indexed triangles, one
instance and base instances 0–14. The ICB inherits its parent's pipeline.

This is a specific prototype, not general support for arbitrary vertex
shaders. The original Apple application, its 15-command scene, actual
drawable/depth configuration and transparent system integration remain
unqualified. The GPU-generated ICB preparation path explicitly refuses this
profile. The application remains responsible for correct resource ordering and
concurrent access.

## GTX qualification

The [auditor](apple-explicit-icb-validation.json) verifies two direct/adapted
pairs: 16 completed render buffers, 196,608 float channels and 8,192 guard
bytes. Direct and adapted images also match the earlier independently recorded
[native reference](APPLE_EXPLICIT_NATIVE.md). The inherited ICB reads either a
shared frame buffer or a private frame buffer populated by a prior blit in the
same command buffer; both use base instances 0 and 1. The image for base 0
matches the CPU's full-target color, and base 1 remains clear.

The auditor checks eight adapted packets and their associated buffer/storage
metadata. Ten expected refusals across the two adapted processes cover short
vertex, object and frame buffers, a misaligned frame offset and an out-of-range
base instance. Each negative command buffer remains unsubmitted. The process
records show the GPU reservation and a bounded set of unchanged system-file
hashes. A missing-blit negative control was not run; successful private-frame
results do not establish the necessity of each synchronization operation.

Two same-archive regressions also pass: [inherited pipeline switching](apple-explicit-icb-inherited-regression.json)
and [writable point draws](apple-explicit-icb-point-regression.json). No
performance comparison was made.

## Reproduce

Obtain the pinned Apple shader and legacy carrier as described in
[the sample gap analysis](APPLE_CPU_ICB_GAP.md). Use fresh output directories
and determine the terminal state of any uncertain process before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
BASELINE='/path/to/recorded-native-reference-run'
python3 tools/build_from_source.py --out build/apple-explicit-icb-new
A="$PWD/build/apple-explicit-icb-new"
E=bridge/experiments/apple_explicit_icb
B="$LAB/results/apple-explicit-icb-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-explicit-icb-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --baseline "$BASELINE" --runs "$LAB/results/apple-explicit-icb-direct-1-new" "$LAB/results/apple-explicit-icb-auto-1-new" "$LAB/results/apple-explicit-icb-direct-2-new" "$LAB/results/apple-explicit-icb-auto-2-new" --out "$LAB/results/apple-explicit-icb-audit-new.json"
```

The Apple metallib hash is tied to the qualified local compiler. Neither the
Apple library nor vendor driver binaries are redistributed.
