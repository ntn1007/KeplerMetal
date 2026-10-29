# Core Video NV12 planes written by Metal on the GTX

A public Core Video/Metal test creates a 128 × 96 `420v` NV12 pixel buffer with
an IOSurface, then maps its luma plane to `R8Unorm` and its interleaved chroma
plane to `RG8Unorm`. The test checks that both Metal textures identify the same
IOSurface as the pixel buffer, identify planes 0 and 1 respectively, and
belong to the GTX 880M. The Core Video texture wrappers stay alive through GPU
completion, as required by [Apple's texture-cache contract](https://developer.apple.com/documentation/corevideo/cvmetaltexturecachecreatetexturefromimage%28_%3A_%3A_%3A_%3A_%3A_%3A_%3A_%3A_%3A%29).

Two Metal compute kernels write distinct deterministic byte patterns to the
planes. The textures reported managed storage, so the test encodes Metal
resource synchronization before waiting for command-buffer completion and
reading the pixel buffer on the CPU. Initial CPU contents are `0x55`; the CPU
never writes the expected result after initialization.

The [auditor](video-cvmetal-nv12-validation.json) checks eight signed, terminal,
serialized processes: two each with both kernels, luma only, chroma only and
no dispatch. All 147,456 captured active bytes match independently generated
CPU expectations. The single-plane cases retain `0x55` on the other plane;
both planes retain it without dispatch. The successful modes account for eight
completed GPU dispatches. Both observed row strides were 128 bytes, so the
padding guard checked **zero** bytes; no padding preservation is claimed.
The same-surface identification and numerical results support this specific
Core Video/Metal sharing path. They do not measure physical transfers or prove
zero-copy operation.

The buffer is synthetic; no compressed video is decoded or encoded in this
test. Earlier hardware-required H.264 encoder attempts returned `-12908`,
including when the GTX registry ID was required, and hardware decode remains
unproved. This result is a building block for processing video frames on Metal,
not a repair of the dedicated video engines or an application-transparent
feature. No performance benchmark was performed. All 83 pinned system-file
hashes were unchanged; the reservation coordinates participating lab runners,
not every user of the display GPU.

## Reproduce

Use the qualified x86_64 macOS, SDK and driver profile. Each command creates a
new result directory and all processes share the existing GPU reservation.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/video_cvmetal_nv12
B="$LAB/results/cvmetal-nv12-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --out "$B"
for n in 1 2; do
  for mode in gpu y-only uv-only none; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/cvmetal-nv12-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --runs "$LAB/results/cvmetal-nv12-gpu-1-new" "$LAB/results/cvmetal-nv12-y-only-1-new" "$LAB/results/cvmetal-nv12-uv-only-1-new" "$LAB/results/cvmetal-nv12-none-1-new" "$LAB/results/cvmetal-nv12-gpu-2-new" "$LAB/results/cvmetal-nv12-y-only-2-new" "$LAB/results/cvmetal-nv12-uv-only-2-new" "$LAB/results/cvmetal-nv12-none-2-new" --out "$LAB/results/cvmetal-nv12-audit-new.json"
```

The GPU programs and signed executable are built locally and are not published.
