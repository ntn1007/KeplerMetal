# Software VideoToolbox decode followed by GTX Metal processing

This experiment connects the previous [synthetic NV12 Metal witness](VIDEO_CVMETAL_NV12.md)
to valid H.264 samples. A VideoToolbox decompression session explicitly disables
hardware decode and requests 320 × 240 IOSurface-backed, Metal-compatible NV12
output. Its six frames come from the previously qualified, locally retained
AVCC fixture. The source pixel buffers are mapped as read-only `R8Unorm` and
`RG8Unorm` Metal textures. The host creates separate IOSurface-backed NV12
buffers for output, checks that source and destination IOSurfaces differ, and
maps their planes for Metal writes.

Two GTX compute kernels invert each luma byte (`255 - Y`) and copy each chroma
byte. This deliberately simple transform tests the bridge; it is not presented
as a useful codec or color-conversion algorithm. Managed destination textures
are synchronized before CPU readback. Source and destination texture wrappers
remain alive until each GPU command buffer completes. The source is re-read to
check that the transform did not modify it. Each frame is submitted and waited
individually; no overlapping-frame or performance conclusion follows.

## Evidence

Two processes each run both kernels, luma only, chroma only and no dispatch.
The independent [auditor](video-vt-cvmetal-validation.json) checks **48 decoded
frames, 48 destination frames, 11,059,200 active bytes and 48 completed GPU
dispatches**. Every decoded source exactly matches the same frame of the
previously recorded FFmpeg CPU reference; every output matches an independent
CPU transformation. In the single-plane controls the unwritten destination
plane stays `0x55`, and in the no-dispatch control both planes stay `0x55`.
The NVIDIA device, distinct surface/plane identities, allowed texture usage,
managed-resource synchronization, signed executables, terminal serialized
processes and 83 pinned system-file hashes are checked.

The FFmpeg 9.0.2 arm64 software reference was generated in the earlier video
transport experiment, not re-executed in this cohort. Its archived executable,
input and output hashes and terminal receipt are checked. The auditor rebuilds
the Annex-B input from the AVCC fixture and checks its hash against that
receipt. The decoded source is a synthetic test clip, not a user's video.

VideoToolbox's `UsingHardwareAcceleratedVideoDecoder` property returned
`-12900` in these runs; that unsupported query is **not** interpreted as a
false result. The session specification explicitly disables hardware decode.
The GPU runs Metal compute on already-decoded images; no dedicated NVIDIA video
decoder or encoder execution, transparent application integration, zero-copy
physical transfer or speedup is established. The prior hardware-required H.264
sessions remain unsuccessful.

## Reproduce

The exact AVCC fixture and archived independent CPU reference/receipts are
private local dependencies. [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md) describes
the fixture and FFmpeg software-reference procedure. This auditor deliberately
pins the original fixture and reference hashes; new compressed input requires a
new qualification rather than silent repinning. Use fresh results and serialize
all GPU processes under the existing reservation.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
FIXTURE='/path/to/pinned-h264-fixture'
REFDIR='/path/to/archived-ffmpeg-reference'
E=bridge/experiments/video_vt_cvmetal
B="$LAB/results/vt-cvmetal-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --fixture "$FIXTURE" --reference "$REFDIR/decoded.nv12" --out "$B"
for n in 1 2; do
  for mode in gpu y-only uv-only none; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/vt-cvmetal-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --reference-evidence "$REFDIR" --runs "$LAB/results/vt-cvmetal-gpu-1-new" "$LAB/results/vt-cvmetal-y-only-1-new" "$LAB/results/vt-cvmetal-uv-only-1-new" "$LAB/results/vt-cvmetal-none-1-new" "$LAB/results/vt-cvmetal-gpu-2-new" "$LAB/results/vt-cvmetal-y-only-2-new" "$LAB/results/vt-cvmetal-uv-only-2-new" "$LAB/results/vt-cvmetal-none-2-new" --out "$LAB/results/vt-cvmetal-audit-new.json"
```

The fixture, generated binaries and frame captures are not distributed in the
public repository.
