# Restricted baseline IDR VP preparation

The [CPU-only adapter](../bridge/experiments/video_bsp_staging/VideoIdr.cpp)
connects the bounded baseline header extractor to the experimental VP picture
model. It accepts only a progressive baseline IDR with zero frame number and
picture-order fields, short-term marking, no output-prior flag and no supplied
prior references. The extracted chroma offset and constrained-intra flag are
included. Because this subset has neither SPS nor PPS scaling-matrix syntax,
the adapter uses flat matrices of 16, consistent with the initialization and
PPS inheritance in [FFmpeg 9.0.2's H.264 parameter-set code](https://github.com/FFmpeg/FFmpeg/blob/n9.0.2/libavcodec/h264_ps.c).

The adapter is a model of one restricted case, **not a full H.264 parser or a
video decoder**. Its caller supplies a logical target identity; no real
reference image, GPU buffer or completed decode is established. The target
state is a proposal and the bytes must not be submitted. The P pictures and
other IDR variants remain outside this adapter, and complete validation,
reference ownership, GPU channels, synchronization and transport are missing.

## Evidence

On the iMac, the retained first IDR picture and its two slice headers produced
one 756-byte block. It matches an independently assembled expectation from the
FFmpeg 9.0.2 `trace_headers` capture and the original pinned Mesa VP helper;
the five P pictures were refused. Synthetic tests exercise chroma offsets,
IDR markers and refusal paths. The existing six-frame baseline header and BSP
regression also passed. [iMac IDR receipt](video-idr-vp-validation.json)
· [baseline regression](video-idr-baseline-validation.json).

The same first IDR, code and test inputs were transferred with verified hashes
to the MacBook: ASan/UBSan passed and the output hash matched the iMac; one P
picture was refused. [MacBook receipt](video-idr-vp-mac-validation.json).
Neither computer executed this block on an NVIDIA video engine.

## Reproduction

Use the private retained fixture, trace and previously generated pinned Mesa
reference with fresh output directories. First run `validate_baseline.py` as
described in [the baseline guide](VIDEO_BSP_BASELINE.md), and
`validate_video_picture.py` as described in [the VP guide](VIDEO_VP_PICTURE.md).
Then:

```sh
E=bridge/experiments/video_bsp_staging
python3 "$E/validate_video_idr.py" --fixture /path/to/fixture \
  --reference /path/to/ffmpeg-trace --baseline /path/to/baseline-result \
  --vp-baseline /path/to/mesa-vp-result --out /path/to/new-idr-result
python3 "$E/validate_video_idr_mac.py" --fixture /path/to/fixture \
  --baseline /path/to/baseline-result --local /path/to/new-idr-result \
  --host SSH_ALIAS --remote-dir /path/to/new/remote-dir --out /path/to/new-mac-result
```
