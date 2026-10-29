# Inherited pipelines and caller state within one render encoder

This GPU cohort extends the [inherited-pipeline test](RENDER_INHERITED_PIPELINE.md).
It uses one render encoder, one previously encoded CPU ICB command, and the
registered smooth, flat and smooth pipelines in succession. Three scissored
draws occupy separate regions. A fourth ordinary draw follows with no pipeline
or vertex-buffer rebinding; it uses a caller vertex buffer distinct from the
ICB's vertex buffer. This distinguishes vertex-buffer restoration; because the
last ICB also uses the parent's pipeline, it does not independently distinguish
pipeline restoration.

Two direct/adapted pairs completed on the GTX 880M. The [auditor](inherited-same-encoder-validation.json)
checks 49,152 float channels and 2,048 guard bytes across four images, verifies
that raw direct/adapted images match, and checks 3,072 red flat pixels plus
3,072 green caller-state pixels against CPU constants. Smooth regions are
checked for finite, bounded interpolated colors, unit channel sums and varying
samples, rather than a complete CPU rasterization oracle. The command traces
show three freshly materialized records with the expected pipeline names and
draw packet, and report resource declarations and record retention. Signed
processes are terminal and nonoverlapping; the pinned system files are
unchanged.

This qualifies the specific side-effect-free test profiles, scissor regions and
one following direct draw. It is not full ICB conformance, a third-party
application test, system integration or a performance benchmark. Other
geometry, state interactions, resources and concurrency remain to be tested.

## Reproduce

Use the exact hash-pinned local assets; the carrier is not redistributed. Use
fresh output paths and establish an uncertain process's terminal state before
retrying. The runtime archive can be built from public sources.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
LEGACY='/path/to/render_state_carrier.metallib'
VERTEX='/path/to/vertex_io_carrier.metallib'
PROFILE='/path/to/cpu_icb_vertex_profiles.json'
python3 tools/build_from_source.py --out build/inherited-same-encoder-new
A="$PWD/build/inherited-same-encoder-new"
E=bridge/experiments/render_inherited_same_encoder
B="$LAB/results/inherited-same-encoder-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$VERTEX" --manifest "$PROFILE" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/inherited-same-encoder-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --archive "$A" --runs "$LAB/results/inherited-same-encoder-direct-1-new" "$LAB/results/inherited-same-encoder-auto-1-new" "$LAB/results/inherited-same-encoder-direct-2-new" "$LAB/results/inherited-same-encoder-auto-2-new" --out "$LAB/results/inherited-same-encoder-audit-new.json"
```
