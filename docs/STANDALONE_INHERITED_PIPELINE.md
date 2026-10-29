# Public Metal client with an inherited render pipeline

This purpose-built client imports only public Metal and Foundation APIs. With
an explicitly injected process-local bootstrap, one CPU-encoded render ICB
inherits two registered pipelines in a single encoder and a following direct
draw uses the caller's vertex buffer. The bootstrap pins the client, shader,
manifest and legacy carrier hashes, recognizes two named vertex/fragment
functions and checks a bounded render-pipeline descriptor. An unrelated
library is forwarded to Metal. The client is independently compiled and does
not link KeplerMetal; `nm -u` checks its imports.

This is not a third-party application test or transparent system integration.
The bootstrap is explicitly injected into this one pinned process; a local
hash is a selection guard, not an independent authorization boundary. It
qualifies one shader library, two pipeline profiles, one command, geometry and
target. The descriptor matcher and behavior are not certified for arbitrary
applications, libraries, descriptors, state changes, threads or OS versions.

## Evidence

The [auditor](standalone-inherited-pipeline-validation.json) checks eight
signed, terminal, nonoverlapping GTX processes. Two direct and two adapted
renders produce identical images: 49,152 checked channels and 2,048 guard
bytes. Red flat and green caller-buffer regions match CPU constants; smooth
regions have bounded, finite, interpolated values but no full CPU rasterizer
oracle. Captured records and packets identify the three pipeline selections.
The native ICB control stops on the missing internal NVIDIA selector before
drawing; changed client, manifest and library controls stop before drawing.

One direct/native-ICB pair of the same client ran on an Apple M1 Max over SSH.
The transferred client source and metallib hashes were verified at both ends;
both M1 images match each other and pass the same region checks. Their raw
floating-point image bits differ slightly from the GTX images. This reference
is not another GTX execution, a performance comparison or a general Metal
conformance test. The M1 run was observed over SSH and is not covered by the
GTX reservation manifest.

During preparation, an earlier wrong-library test passed missing shader
functions to Metal and terminated on a descriptor-validation assertion
before GPU submission. The final client checks function availability first;
the final wrong-library control stops before creating that invalid pipeline.
No installed driver or framework was modified. The listed system-file hashes
are a bounded check, not a complete system inventory.

## Reproduce

Use fresh directories and locally obtained pinned assets. A process whose
terminal state is unknown must be resolved before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
LEGACY='/path/to/render_state_carrier.metallib'
SHADER='/path/to/vertex_io_carrier.metallib'
MANIFEST='/path/to/cpu_icb_vertex_profiles.json'
WRONG='/path/to/wrong-transform.metallib'
python3 tools/build_from_source.py --out build/public-inherited-new
A="$PWD/build/public-inherited-new"
E=bridge/experiments/standalone_inherited_pipeline
B="$LAB/results/public-inherited-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --shader "$SHADER" --manifest "$MANIFEST" --wrong-shader "$WRONG" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/public-inherited-$mode-$n-new"
  done
done
for mode in native wrong-client wrong-manifest wrong-library; do
  python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/public-inherited-$mode-new"
done
python3 "$E/audit.py" --build "$B" --archive "$A" --m1 '/path/to/recorded-m1-captures' --runs "$LAB/results/public-inherited-direct-1-new" "$LAB/results/public-inherited-auto-1-new" "$LAB/results/public-inherited-direct-2-new" "$LAB/results/public-inherited-auto-2-new" "$LAB/results/public-inherited-native-new" "$LAB/results/public-inherited-wrong-client-new" "$LAB/results/public-inherited-wrong-manifest-new" "$LAB/results/public-inherited-wrong-library-new" --out "$LAB/results/public-inherited-audit-new.json"
```

The M1 reference was built with `xcrun clang++ -O2 -std=c++17 -fobjc-arc
client.mm -framework Metal -framework Foundation -o application`, signed
ad hoc and run as `application vertex_io_carrier.metallib OUTPUT direct`
and `application vertex_io_carrier.metallib OUTPUT icb`. Separate output
directories are required; record hashes, host/toolchain and process outcomes.
