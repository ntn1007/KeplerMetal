# GPU access to a Metal buffer after purge and restoration

The existing NVIDIA Metal driver executes a bounded post-purge read/write test on the GTX 880M. This qualifies an existing API path for the tested profile; it is not a new driver implementation, a performance benchmark, a proof of memory reclamation or a video test.

In each post-purge trial, a fresh process creates a 4 MiB shared `MTLBuffer`, confirms `NonVolatile`, marks it `Empty`, observes `Empty`, restores `NonVolatile`, and queries the restored state. The CPU then initializes every one of its 1,048,576 uint32 values with a new pattern. The old contents are not checked or assumed to survive. Two ordinary native Metal compute encoders, in order in a single command buffer, run the existing [resource-sync kernels](../bridge/src/resource_sync_probe.metal):

1. `consume` reads the restored buffer and writes a separate output buffer.
2. `produce` overwrites the restored buffer with a different index-dependent pattern.

After command completion, both full buffers are captured locally. A separate Python oracle computes the expected uint32 values independently and checks every output, every overwritten target value, and 64-byte output guards on both sides. On three post-purge processes and three interleaved processes with no purge, all 12,582,912 positive uint32 comparisons passed; all six pairs of captures had identical hashes. Across all seven processes, 896 guard bytes passed. The guard is on the separate output buffer; it is not a general out-of-bounds proof for the target.

A seventh process initializes the same buffers but deliberately submits **no** command buffer. Its two captures retain their CPU-initialized values. The CPU oracle checks that every one of the 1,048,576 words in each capture differs from the corresponding GPU result. This control demonstrates that the expected GPU effects cannot be mistaken for initialization in this case. The six positive hosts report completed command buffers. Exact device registry ID, NVIDIA PCI ancestor, UID, system profile, Metal library and host hashes are verified. The installed driver is unchanged; no private resource-manager calls or injected GPU programs are used.

The [sanitized audit](video-metal-purge-gpu-validation.json) records source/build and Metal-library fingerprints, result and manifest hashes, per-process captures, controls, signatures and ordering. Raw buffer contents and signed executables remain in the local lab. The audit reruns the independent CPU oracle over the raw files, verifies the signatures and rejects different builds, devices, captures, overlapping processes or a failed original oracle. The on-disk driver components are hash-checked and loaded kernel extensions are checked by UUID; this does not compare loaded kernel code bytes or independently pin all compiler components.

This result does not demonstrate whether `Empty` reclaimed physical memory, whether any resource was destroyed, preservation of contents across an empty state, asynchronous/multi-queue behavior, support for every storage mode, or a speedup. The earlier [CPU-only purge observations](VIDEO_METAL_PURGE.md) and their process-local IOKit instrumentation are separate: this GPU cohort does not use that observer.

## Reproduction on the pinned machine

Use the cooperative lab reservation root, obtain a fresh GPU registry ID from the [resource observer inventory](VIDEO_METAL_RESOURCE_OBSERVER.md), and choose new output names. The output captures occupy about 8 MiB per process. Builds do not dispatch GPU work. An abnormal host, changed profile, nonterminal reservation or failed oracle requires inspection before any further dispatch.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<fresh GPU registry ID>'
python3 bridge/tools/video_metal_purge_gpu.py build --out "$LAB/results/purge-gpu-build-new"
for item in negative:01 native:01 purge:01 native:02 purge:02 native:03 purge:03; do
  mode=${item%:*}
  number=${item#*:}
  python3 bridge/tools/video_metal_purge_gpu.py run \
    --build "$LAB/results/purge-gpu-build-new" \
    --out "$LAB/results/purge-gpu-${mode}-${number}" \
    --reservation-root "$LAB" --mode "$mode" --registry-id "$RID" || break
done
python3 bridge/tools/audit_video_metal_purge_gpu.py \
  "$LAB/results/purge-gpu-negative-01" \
  "$LAB/results/purge-gpu-native-01" "$LAB/results/purge-gpu-purge-01" \
  "$LAB/results/purge-gpu-native-02" "$LAB/results/purge-gpu-purge-02" \
  "$LAB/results/purge-gpu-native-03" "$LAB/results/purge-gpu-purge-03"
```
