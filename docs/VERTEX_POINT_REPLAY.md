# Process-local replay of native point draws with vertex writes

A laboratory client records an ordinary native Metal **point** draw into an
uncommitted preparation encoder, reads the driver's 24-byte draw packet, and
copies that verified packet over a one-point primer draw in its own uncommitted
consuming encoder. It then submits only the consuming command buffer. The
pipeline uses the [previously tested](VERTEX_VOID_WRITE.md) `void` vertex
shader with rasterization disabled and an atomic write to a bound buffer.
This is a prototype of command transport, not an implementation of Metal ICBs or
an integration into the KeplerMetal adapter.

For the pinned NVIDIA stack and shader, the observed draw packet uses method
`0x3830`, with primitive value 0 for points and the requested vertex count.
This differs from the `0x3aa0` stage-in path tested for certain vertex-input
pipelines. The recorded packet has no buffer address; the ordinary native
encoder binds the actual buffer before the packet is inserted. No GPU program
binary or system component is replaced. The client checks cursor identity,
capacity, exact primer/record words, write protection, copied bytes and the
preparation buffer's uncommitted status. This private cursor ABI is tied to the
pinned stack and is not portable.

## Validation

Two signed direct processes and two signed replay processes each ran counts 0
through 5. All 24 consuming command buffers completed. Direct and replay masks
were `0, 1, 3, 7, 15, 31`; in replay mode every primer requested one vertex, so
counts 0 and 2–5 provide controls that the submitted draw is not just the
primer. The client reported 3,072 intact guard bytes in total. The independent
[auditor](vertex-point-replay-validation.json) checked process and build hashes,
serial reservation receipts, all captured packet words and the reported masks.
Raw buffer snapshots were not retained and the auditor verifies the client
reports, not the GPU execution independently. Individual invocations cannot be
counted from an atomic OR mask.

This proves neither general writable shader safety nor writable-buffer support
in the current ICB adapter. The test uses one shader, one shared buffer at one
offset, one instance and no concurrent work; resource residency, memory
ordering, buffer lifetime, indexed/indirect paths and application compatibility
still require their own qualification. The audit establishes that specified
system components remained unchanged, not that every system file was checked.
No speed measurement was performed.

## Reproduce

Use the same pinned driver profile and shared lab reservation. Outputs must be
fresh; a process of unknown status must be inspected before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/vertex_point_replay
B="$LAB/results/point-replay-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --out "$B"
for n in 1 2; do
  for mode in direct replay; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/point-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --runs "$LAB/results/point-direct-1-new" "$LAB/results/point-replay-1-new" "$LAB/results/point-direct-2-new" "$LAB/results/point-replay-2-new" --out "$LAB/results/point-replay-audit-new.json"
```
