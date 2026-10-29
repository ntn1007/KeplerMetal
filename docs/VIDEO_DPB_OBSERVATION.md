# Software H.264 reference snapshots versus VP proposals

On the retained six-picture H.264 fixture, FFmpeg 9.0.2 decoded six frames on the MacBook CPU with one decoder thread and `-hwaccel none`. Its debug output records the short-term reference state immediately before each of the 12 slice reports. For each P picture, both slices report the same reference numbers as the experimental VP block, but FFmpeg's short-term array is **newest first** while our proposal stores them **oldest first**:

| Picture | FFmpeg short-term state | VP proposal table |
| --- | --- | --- |
| P1 | 0 | 0 |
| P2 | 1, 0 | 0, 1 |
| P3 | 2, 1 | 1, 2 |
| P4 | 3, 2 | 2, 3 |
| P5 | 4, 3 | 3, 4 |

FFmpeg reports POC values 65536 through 65546 while the proposed values are 0 through 10; for these pictures the difference is consistently 65536. [FFmpeg's IDR initialization](https://github.com/FFmpeg/FFmpeg/blob/n9.0.2/libavcodec/h264dec.c) sets the previous POC MSB to `1 << 16`; this is source context for an implementation-specific representation, not proof that NVIDIA wants either value. The [short-term debug output](https://github.com/FFmpeg/FFmpeg/blob/n9.0.2/libavcodec/h264_refs.c) prints FFmpeg's internal reference array; it is not a capture of the NVIDIA command interface or necessarily the active reference list.

The matching **sets** support the fixture's simulated sliding-window assumption. They do not prove that VP table order, absolute POC convention, GPU surface ownership or synchronization is correct for NVIDIA. Do not reverse entries or change POC solely on this observation, and do not submit these blocks to the GPU. The separate Mesa helper matched the original table order in the [previous CPU test](VIDEO_PREDICTIVE_PICTURE.md), but it too is not a live NVIDIA oracle.

The run produced six yuv420p frame hashes, each matching the corresponding frame of an earlier retained software FFmpeg NV12 decode after lossless planar/interleaved rearrangement. The earlier decode used a different pinned FFmpeg executable, not a different decoder implementation; this is not independent hardware verification. The runner ignores the separate stream-probe decoder and checks the later decoder context, exact binary and input hashes before and after the run, and proposal-block hashes. The logs stay private; the [sanitized receipt](video-dpb-observation-validation.json) records hashes and derived numbers. No system files, GPU video engine or OCLP were modified or exercised.

## Reproduction

Use the retained private fixture and existing [predictive result](VIDEO_PREDICTIVE_PICTURE.md), the earlier software NV12 reference, a fresh output directory and an authenticated arm64 SSH host with the exact pinned FFmpeg executable. This is CPU-only; no Qwen model or GPU reservation is used.

```sh
python3 bridge/experiments/video_dpb_observation/observe.py \
  --host SSH_ALIAS --remote-ffmpeg /absolute/path/to/ffmpeg \
  --remote-fixture /absolute/path/to/fixture-annexb.h264 \
  --reference-nv12 /absolute/path/to/retained-decoded.nv12 \
  --predictive /absolute/path/to/predictive-result \
  --out /absolute/path/to/new-observation
python3 -m unittest discover -s tests -p 'test_video_dpb_observation.py'
```

The runner deliberately pins the software executable, fixture and pixel reference. A different build needs an independently reviewed profile and must not be presented as this exact result.
