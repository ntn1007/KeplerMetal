# Point-write render-to-compute dependency

A GPU consumer can read the output of the certified point-write vertex shader
in the following compute pass, for the two arrangements tested on the GTX 880M:

- Render and compute encoders in one command buffer.
- A committed render command buffer followed by a compute command buffer on
  the same `MTLCommandQueue`.

The test uses the existing [certified point-write CPU ICB profile](VERTEX_POINT_ADAPTER.md)
and compares it with the same shader called directly through Metal. The input
and output are separately allocated shared `MTLBuffer` objects with the default
resource options. The consumer atomically loads the input and writes its value
XOR `0xc0de0000` to the output. The CPU initializes both buffers before encoding
and reads them only after the consumer completes; it does not wait between the
producer and the consumer commit.

Two direct/adapted process pairs exercised vertex counts 1, 3 and 5 for both
arrangements: 24 positive cases total. Four no-producer controls returned the
zero-input consumer value. The [independent auditor](vertex-point-dependency-validation.json)
checked 56 captured raw input/output buffers, 7,168 guard bytes, process and
archive hashes, adapted command packets and direct/adapted equality. The client
reported both command buffers completed. The control confirms the consumer's
zero-input result in this setup; it does not prove precisely which mechanism
provided ordering. The GPU may have completed the producer before the consumer
was submitted; actual overlap was not measured.

Apple describes [automatic resource synchronization](https://developer.apple.com/documentation/metal/resource-synchronization)
for directly bound tracked resources and `MTLCommandQueue`, and states that
resources created from a device default to tracked behavior. This experiment
tests only the observed configuration. It does not establish cross-queue,
untracked-heap, Metal 4 queue, concurrent CPU access, aliasing, arbitrary
shader, or general resource-lifetime behavior. No performance claim is made.
The checked system components were unchanged; the runners do not inventory all
system files. All GPU clients were signed, terminal and serialized through the
cooperative reservation.

## Reproduce

Use the same pinned locally built shader, manifest, legacy carrier, runtime
archive and system profile described in [the point adapter reproduction](VERTEX_POINT_ADAPTER.md).
Use fresh directories; establish a process's terminal state before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
LEGACY='/path/to/render_state_carrier.metallib'
SHADER='/path/to/point.metallib'
A='/absolute/path/to/built-runtime-archive'
E=bridge/experiments/vertex_point_dependency
B="$LAB/results/point-dependency-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$SHADER" --manifest "$PWD/bridge/experiments/vertex_point_adapter/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/point-dependency-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --archive "$A" --runs "$LAB/results/point-dependency-direct-1-new" "$LAB/results/point-dependency-auto-1-new" "$LAB/results/point-dependency-direct-2-new" "$LAB/results/point-dependency-auto-2-new" --out "$LAB/results/point-dependency-audit-new.json"
```
