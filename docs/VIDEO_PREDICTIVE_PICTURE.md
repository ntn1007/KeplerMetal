# Restricted H.264 P-picture parameter preparation

The CPU-only [predictive adapter](../bridge/experiments/video_bsp_staging/VideoPredictive.cpp) extends the existing IDR experiment with a separately called `prepare_baseline_p`. It prepares a VP parameter proposal for a narrow progressive baseline P-picture subset. The original IDR adapter still refuses P pictures. This is an experimental model, not a decoder or a complete bitstream validator; its output **must not be submitted to a GPU**.

The accepted subset requires POC type 0, reference pictures, no frame-number gaps or wrap, `poc_lsb == 2 * frame_num`, two maximum short-term references, no weighted prediction, list modification or adaptive marking, and a caller-supplied chronological sliding reference window with one reference for frame 1 and two thereafter. Logical reference identities and slots must be distinct from a fresh target. The caller asserts that these references are already decoded: this model cannot establish their actual surface ownership, contents or completion. The header extractor only probes the relevant prefix, not the complete H.264 syntax. It rejects out-of-scope inputs rather than authorizing GPU execution.

## Evidence and limits

For one existing IDR-plus-five-P fixture, ten P-slice headers were checked against an archived FFmpeg 9.0.2 `trace_headers` capture. Five 756-byte proposals matched a Python reconstruction using the traced fields and the assumed reference sequence, and separately matched the pinned Mesa 26.2.4 VP helper. The fixture harness explicitly simulates completion of each logical reference. These comparisons establish neither the real FFmpeg decoded picture buffer sequence nor actual GPU reference lifetimes. [iMac receipt](video-predictive-picture-validation.json); [baseline regression](video-predictive-baseline-regression.json); [IDR regression](video-predictive-idr-regression.json).

The exact sources and fixture were hash-checked before and after transfer to an arm64 MacBook. Baseline, IDR and predictive CPU unit tests passed with ASan/UBSan; all five output hashes matched the iMac. [MacBook receipt](video-predictive-picture-mac-validation.json). No NVIDIA video engine, GPU transport, real decode or system change was involved. VideoToolbox's previously observed failure is not repaired by this result.

The reference-state model and serializer are project code; FFmpeg's [slice handling](https://github.com/FFmpeg/FFmpeg/blob/n9.0.2/libavcodec/h264_slice.c) and [reference handling](https://github.com/FFmpeg/FFmpeg/blob/n9.0.2/libavcodec/h264_refs.c) offer context, not proof that the simulated state was decoded. Mesa's exact reference source is generated locally from the separately obtained revision identified in [the VP guide](VIDEO_VP_PICTURE.md); it is not distributed here.

## Reproduction

Obtain the retained private fixture and trace, prepare the baseline and pinned Mesa reference as in [the baseline guide](VIDEO_BSP_BASELINE.md) and [VP guide](VIDEO_VP_PICTURE.md), then rerun the IDR regression as in [its guide](VIDEO_IDR_VP.md), using this exact checkout and fresh output directories. The predictive and MacBook checks are:

```sh
E=bridge/experiments/video_bsp_staging
python3 "$E/validate_video_predictive.py" --fixture /path/to/fixture \
  --reference /path/to/ffmpeg-trace --baseline /path/to/baseline-result \
  --idr-regression /path/to/idr-result --vp-baseline /path/to/mesa-vp-result \
  --out /path/to/new-p-result
python3 "$E/validate_video_predictive_mac.py" --fixture /path/to/fixture \
  --baseline /path/to/baseline-result --idr-regression /path/to/idr-result \
  --local /path/to/new-p-result --host SSH_ALIAS \
  --remote-dir /path/to/new/remote-dir --out /path/to/new-mac-result
```

The Mac check transfers only its source and fixture inputs to the specified SSH host; output directories must be new. These tests do not reserve or execute a GPU.
