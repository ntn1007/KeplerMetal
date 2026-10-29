# Native GTX execution of the Apple CPU ICB sample shader

The unchanged, locally obtained Apple sample shader documented in
[the gap analysis](APPLE_CPU_ICB_GAP.md) was compiled with the local Metal
toolchain and used by an original headless direct-render client. It binds the
three explicit vertex buffers through ordinary native Metal calls. This does
not run the Apple sample application or exercise the ICB adapter.

Two signed, terminal, nonoverlapping GTX processes each rendered four cases:
`baseInstance` 0 or 1, with frame state either in a shared buffer or in a
private buffer populated by an earlier blit in the **same command buffer**.
The vertex and object data make object 0 cover the target and move object 1
outside it. An independent [auditor](apple-explicit-native-validation.json)
checks 98,304 floating-point channels against CPU constants, 4,096 guard bytes
and eight native draw packets. The base-0 image is uniformly `(0.25, 0.75, 0, 1)`;
the base-1 image remains clear. Shared and private-frame images match for each
base value.

The observed second-draw packet has the existing triangle method `0x3aa0` and
preserves `baseInstance`; its encoding was read before the command buffer was
submitted and was not modified. Each render contains two identical native
draws. This is evidence for these particular command and input profiles, not a
general packet specification. The private-frame result confirms that this
sequence completes correctly; without a missing-blit control it does not prove
that every individual synchronization operation was necessary. No performance
comparison was made, and only a bounded set of system-file hashes was checked.

This establishes a native reference for implementing explicit-buffer bounds,
registration and ICB execution. It does not yet implement those features.

## Reproduce

Use the locally obtained, hash-pinned Apple sample and carrier from the
[gap experiment](APPLE_CPU_ICB_GAP.md). Rebuild the public runtime if needed.
Use fresh output paths and inspect terminal process state before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-native-new
A="$PWD/build/apple-native-new"
E=bridge/experiments/apple_explicit_native
B="$LAB/results/apple-native-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$S/apple-empty-stage-manifest.json" --out "$B"
for n in 1 2; do
  python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode direct --out "$LAB/results/apple-native-$n-new"
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-native-1-new" "$LAB/results/apple-native-2-new" --out "$LAB/results/apple-native-audit-new.json"
```

The library pin depends on the qualified toolchain. The source, shader and
runtime artifacts are compiled locally; the Apple sample is not redistributed.
