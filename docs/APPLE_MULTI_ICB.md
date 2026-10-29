# Fifteen Apple-shader commands in one scoped ICB

An adapted test client uses the exact Apple sample shader with 15 distinct
vertex buffers, a shared 15-entry object-parameter buffer and an inherited
pipeline. Each CPU-encoded ICB slot draws a triangle with a different
`baseInstance`. A single ICB is reused for two successive frame-state values;
the test runs separately with a shared frame buffer and a private frame buffer
populated by an earlier blit in the same command buffer.

This is a synthetic scene that matches the sample's command count and buffer
roles; it is **not** the Apple application's original geometry, drawable,
depth state or view. It uses the scoped prototype, the pinned library and
manifest, and a 64×48 floating-point target. General ICB support, transparent
application integration and GPU-encoded ICBs remain unqualified.

A [subsequent offscreen profile](APPLE_VIEW_ICB.md) adds BGRA color, a depth
attachment and back-face cull state, while retaining the same qualification
limits for the original application.

## Evidence

Two direct/adapted pairs on the GTX produce 16 completed render buffers. The
[audit](apple-multi-icb-validation.json) compares 196,608 float channels and
8,192 guard bytes; all direct and adapted raw images match. It independently
checks 240 expected object-center pixels, confirms all 15 distinct object
colors are present, and verifies that the frame update changes the image while
the shared/private variants match. It does not implement a complete CPU
rasterizer or prove the necessity of every synchronization step.

The adapted executions contain 120 verified draw packets. For every 15-command
execution the auditor checks ordered base instances 0–14, 15 distinct mesh
addresses, one object buffer and one frame buffer, plus declared resource
usage and record retention. A short object buffer causes slot 14 to be refused
before submission in both adapted processes. The earlier 14 slots have already
been materialized into unsubmitted intermediate records; that is not GPU
execution and is not evidence of an atomic CPU-side preparation rollback.
The negative command buffer is not submitted. The audit checks signed terminal
processes, nonoverlapping reservations and selected system-file hashes.

The client waits for each frame before changing the source buffer; it does not
test overlapping frames or concurrent mutation. There is no missing-blit
negative control or performance comparison. The original Apple app has not
been executed by this experiment.

## Reproduce

Obtain the pinned shader and carrier as described in
[the earlier gap analysis](APPLE_CPU_ICB_GAP.md). Use fresh paths and verify a
process's terminal state before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-multi-icb-new
A="$PWD/build/apple-multi-icb-new"
E=bridge/experiments/apple_multi_icb
B="$LAB/results/apple-multi-icb-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-multi-icb-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-multi-icb-direct-1-new" "$LAB/results/apple-multi-icb-auto-1-new" "$LAB/results/apple-multi-icb-direct-2-new" "$LAB/results/apple-multi-icb-auto-2-new" --out "$LAB/results/apple-multi-icb-audit-new.json"
```

The local compiler must reproduce the pinned Apple library hash. Apple source,
compiled library and vendor driver binaries are not redistributed here.
