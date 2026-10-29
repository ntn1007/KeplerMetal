# Public Metal mixed compute/render client

A separately compiled client library uses public Foundation and Metal calls to encode a compute operation followed by an indexed render operation on one command buffer. The private index buffer is produced by the GPU and consumed by the GPU without an intervening CPU read. A separate host explicitly installs a KeplerMetal scope, registers the pinned compute and render profiles, enables both automatic factories on one queue and supplies their pipeline objects. `nm -u` confirms the client library has no KeplerMetal or `KPCPU` imports. The client was written for this experiment: it is **not** an existing third-party application, automatic system integration or a replacement driver.

The client encodes ordinary Metal direct commands or CPU-encoded indirect command buffers. The direct control uses the same scoped queue and registered pipeline objects, but issues native direct dispatch and draw calls. Both modes use the same private buffers, scissor and shader; the scope adapts encoder factories in both cases.

## GTX evidence

Eight separately signed host processes ran serially under the cooperative GPU reservation: two each for direct, indirect, no compute producer and no render consumer. Each uses the same separately signed client library. An independent audit checks **98,304 float channels**, image and buffer guard bytes, the actual indices and the GPU atomic counter. Direct and indirect images, indices and counter values agree byte for byte across both pairs. Each active compute case reports 32 GPU invocations and the rendered scissor contains 117 colored pixels. Without the producer the counter is zero and the initialized indices remain unchanged; without the render consumer the counter reaches 32 but the image stays blank. These controls also repeat exactly. [Sanitized receipt](public-mixed-client-validation.json).

The host verifies the PCI identity `10de:1198`, restores its device and queue objects and compares five shared native method implementations before scope installation and after restoration. The auditor checks client and host hashes/signatures, nonoverlapping reservations, terminal process states and the automatic/indirect event records. The reservation covers participating laboratory runners, not every system GPU user. The checked image and guard data do not establish the complete Metal ICB contract or general shader compatibility. No performance gain, unmodified application support, visible presentation or hardware video decoding is claimed. System drivers and OCLP were not changed.

## Reproduce

Obtain the exact pinned compute and render metallibs as in [DUAL_AUTOMATIC_FACTORIES.md](DUAL_AUTOMATIC_FACTORIES.md), and use the matching local driver/SDK profile and a shared laboratory reservation. The separately compiled client is signed locally; no vendor binaries or captured command streams are distributed here. Use fresh build and run directories, execute sequentially and resolve any unknown process outcome before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/public_mixed_client
python3 tools/build_from_source.py --out build/public-mixed-new
A="$PWD/build/public-mixed-new"
B="$LAB/results/public-mixed-build-new"
python3 "$E/experiment.py" build --library "$A" \
  --compute /path/to/cpu_icb_gpu_indices.metallib \
  --render /path/to/render_state_carrier.metallib --out "$B"
runs=()
for n in 1 2; do
  for mode in direct icb no-producer no-render; do
    out="$LAB/results/public-mixed-$n-$mode-new"
    python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" || exit 1
    runs+=("$out")
  done
done
python3 "$E/audit.py" --library "$A" --build "$B" --runs "${runs[@]}" \
  --out "$LAB/results/public-mixed-audit-new.json"
```
