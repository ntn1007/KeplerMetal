# Inherited pipeline for scoped CPU render ICBs

The scoped render adapter accepts `inheritPipelineState = YES` for a bounded
CPU-encoded render ICB. At each execution it reads the parent encoder's current
registered render pipeline and prepares a new record for that pipeline. It does
not reuse an earlier pipeline's record. A command cannot set its own pipeline
in this mode; CPU snapshot copies between differing inheritance modes are
refused. GPU-indirect preparation refuses inherited pipeline commands.

This is a **process-local, explicitly enabled prototype**, not a modification of
the installed NVIDIA driver. Apple documents that inherited commands use the
parent encoder's pipeline and applications should not set a pipeline on those
commands ([Apple property documentation](https://developer.apple.com/documentation/metal/mtlindirectcommandbufferdescriptor/inheritpipelinestate)).
The [Apple CPU ICB sample](https://developer.apple.com/documentation/metal/encoding-indirect-command-buffers-on-the-cpu)
uses this pattern. The sample itself has not been run or qualified here.

## GTX evidence

The [independent audit](inherited-pipeline-validation.json) verifies two
direct/adapted pairs: twelve completed GPU render buffers, 147,456 float
channels, 6,144 guard bytes, signed process identity and nonoverlapping
reservations. One indirect command is encoded once and executed on three
separate render encoders with registered `smooth`, `flat`, then `smooth`
pipelines. The raw direct and adapted images match; the flat image differs
from the smooth image, and the last smooth image matches the first. The auditor
checks finite channels and alpha, the recorded pipeline names and the native
draw packets; this comparison is against direct GPU output, not a full CPU
pixel oracle. The pre-change adapter rejects the descriptor; its direct
control produces the same images.

Fourteen expected refusals cover command-level pipeline setting, incomplete
triangle counts, missing parent pipeline, a snapshot copy between differing
inheritance modes, and inherited buffers. The count is aggregated by the
client; it does not separately record each exception reason. The checked system
files remained unchanged.

On the same rebuilt archive, earlier [trailing triangle](inherited-pipeline-trailing-regression.json)
and [writable point](inherited-pipeline-point-regression.json) suites pass.

The test uses one side-effect-free shader library, two registered profiles,
one command and one triangle, on separate render encoders. A subsequent
[same-encoder cohort](RENDER_INHERITED_SAME_ENCODER.md) also checks pipeline
switching and a following direct draw. Indexed draws, inherited buffers, compute inheritance, GPU
generated commands, concurrent use, unregistered pipelines, arbitrary shaders
and transparent application integration are not qualified. Legacy inherited
pipelines and indexed inherited draws are explicitly refused. No performance
comparison was made.

## Reproduce

Use fresh output directories, exact local hash-pinned assets and the existing
baseline archive/captures; proprietary assets are not redistributed. Do not
retry an uncertain process before its terminal state is established.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
LEGACY='/path/to/render_state_carrier.metallib'
VERTEX='/path/to/vertex_io_carrier.metallib'
PROFILE='/path/to/cpu_icb_vertex_profiles.json'
OLD_ARCHIVE='/path/to/recorded-baseline-archive'
OLD_BUILD='/path/to/recorded-baseline-build'
OLD_DIRECT='/path/to/recorded-baseline-direct'
OLD_AUTO='/path/to/recorded-baseline-auto'
python3 tools/build_from_source.py --out build/inherited-new
A="$PWD/build/inherited-new"
E=bridge/experiments/render_inherited_pipeline
B="$LAB/results/inherited-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$VERTEX" --manifest "$PROFILE" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/inherited-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --archive "$A" --baseline-archive "$OLD_ARCHIVE" --baseline-build "$OLD_BUILD" --baseline-direct "$OLD_DIRECT" --baseline-auto "$OLD_AUTO" --runs "$LAB/results/inherited-direct-1-new" "$LAB/results/inherited-auto-1-new" "$LAB/results/inherited-direct-2-new" "$LAB/results/inherited-auto-2-new" --out "$LAB/results/inherited-audit-new.json"
```
