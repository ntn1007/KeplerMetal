# Public codec tests after the AppleVA eligibility result

The process-local model entry that makes the pinned VP3 availability query
succeed does **not** fix the tested public H.264 or MPEG-2 hardware-decoder path.
Both valid bitstreams decode correctly in software on the iMac. All nine
hardware-required creates still return -12906 before producing an image.

This narrows branch A's video investigation. It adds no hardware decoder,
installed-driver patch, Metal capability or measured performance improvement.

## Method and actual observations

The host checks the same resident AppleVA UUID and three code hashes as the
[availability experiment](VIDEO_ELIGIBILITY.md), then calls the public
VideoToolbox API directly. It does **not** call `VP3IsAvailable` first or invoke a
private factory/decoder. The linked observer is confined to the configuring
thread, one pinned native policy callsite and an explicit synthetic calibration.

Fresh processes compare the original table, a minimal table with a different
model, and the same table with `iMac11,1`. The expected synthetic replacements
are observed. The native policy callsite is **not observed on that thread** in
any of these codec requests. This says nothing about unobserved threads,
processes or other policy-read mechanisms.

| Codec / artifact | Native processes | Software images and exact bytes | Hardware-required failures |
| --- | --- | --- | --- |
| H.264, first host | 6 | 6 / 691,200 | 4 × -12906 |
| H.264, final extended host | 2 | 6 / 691,200 | 1 × -12906 |
| MPEG-2, final host | 6 | 6 / 691,200 | 4 × -12906 |

The remaining two processes are inspect-only preflights. All fourteen native
processes are terminal, nonoverlapping and use the original shared lab lease.
The three CPU controls produce 18 images / 2,073,600 active NV12 bytes with zero
differences. Each hardware attempt produces zero images. Exit zero means a
completed diagnostic; the hardware-decoder outcome remains a failure.

The first H.264 artifact retains its original source/configuration. The final
host adds an explicit codec field and a selected decoder client; its two fresh
H.264 regression processes are recorded separately. Earlier results are not
silently assigned to the later executable.

## Independent MPEG-2 reference

The existing pinned FFmpeg 9.0.2 and ffprobe binaries on the arm64 reference host
run three bounded commands: software MPEG-2 encoding, software decoding and
packet inspection. No Qwen/MLX service or system setting changes. The original
generator, source transfer and returned file hashes are checked separately.

The input is six original 320×240 NV12 patterns made of constant macroblocks.
This avoids unnecessary IDCT variability while exercising nonconstant luma,
chroma and frame ordering. Every compressed packet is independently decodable;
ffprobe's packet positions and hashes match contiguous file slices exactly.

- Compressed stream: 11,871 bytes, SHA-256
  `e5758154a91053776bbce3d15f5e2a52f78de005d3d86319d6c913bd38276f52`.
- Software decoded output: six images / 691,200 bytes, SHA-256
  `882c66a3f07501919430ecf4df55cbdd0947af2448de2892bfb3c969866b8dee`.

The iMac software result matches those decoded bytes, rather than an assumed
lossless comparison to the unencoded input. This qualifies this fixture, not
general MPEG-2 conformance. The H.264 reference reuses the earlier independent
FFmpeg software result. No M1 GPU result is claimed.

## Next decision point

Bounded offline inspection of the UUID-matched VideoToolbox cache identifies
the 26-byte public `VTDecompressionSessionCreate` wrapper and its 6,538-byte
implementation. The latter contains an error-reporting site with -12906. Its
region hash is recorded in the [validation summary](video-codec-validation.json).
The vendor regions and disassembly stay outside this repository.

This static result **does not prove which error branch ran** or why a decoder
was not chosen. The next experiment should observe forwarded error-reporting or
decoder-selection calls in our public-codec process, with a validated ABI-neutral
observer. No unknown private factory needs to be called or system file changed.

The 83 existing system-file pins, the additional policy file, OCLP and 36 common
runtime sources remain unchanged. Benchmark and system deployment are **NOT RUN**.
Hardware-video execution remains unproved. The complete hardware goal stays open.

## Reproduction

Generate the original MPEG-2 fixture using existing, explicitly pinned external
tools; the generator refuses different hashes and existing output directories:

```sh
python3 bridge/tools/generate_mpeg2_reference.py \
  --ffmpeg /absolute/path/to/ffmpeg --ffprobe /absolute/path/to/ffprobe \
  --expected-ffmpeg VERIFIED_SHA256 --expected-ffprobe VERIFIED_SHA256 \
  --out /new/reference-directory
```

On the exact inspected iMac profile, from `bridge`, build and inspect first:

```sh
python3 tools/native_video_public.py build --codec MPEG2Video \
  --fixture /absolute/path/to/reference-directory/fixture --out results/new-codec-build
python3 tools/native_video_public.py run --build results/new-codec-build \
  --out results/new-codec-inspect --mode inspect
```

After inspecting the pins, run `cpu`, `native`, `wrong-model` and `model-entry`
with a fresh output directory each time. `--codec H264` selects the existing
thirteen-file H.264 fixture. Changed profiles are refusals, not permission to
repin automatically. The historical `audit_video_codecs.py --lab-root
/absolute/path/to/original/bridge --out /new/audit.json` requires omitted private
receipts and pixels. Its corrected lab/public sources yield identical summaries;
the first failed offline audit is retained privately.

Apple documents the separate contracts for
[requiring hardware](https://developer.apple.com/documentation/VideoToolbox/kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder)
and [explicitly disabling it](https://developer.apple.com/documentation/VideoToolbox/kVTVideoDecoderSpecification_EnableHardwareAcceleratedVideoDecoder).
Those contracts define these controls; they do not establish NVIDIA compatibility.
