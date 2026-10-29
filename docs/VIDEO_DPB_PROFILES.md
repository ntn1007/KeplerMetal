# H.264 reference ordering and POC candidate profiles

The earlier software observation found FFmpeg's short-term reference array in newest-first order and POC values offset by 65536. The published FFmpeg 9.0.2 [VA-API H.264 code](https://github.com/FFmpeg/FFmpeg/blob/n9.0.2/libavcodec/vaapi_h264.c) constructs `ReferenceFrames` by traversing the short-term array, followed by long-term entries; it copies the picture's field POCs. This is distinct from the per-slice active reference lists. The pinned Mesa 26.2.4 [VA frontend](https://gitlab.freedesktop.org/mesa/mesa/-/blob/96cb43121031992b85767f9c1be8f3f48e22b1d2/src/gallium/frontends/va/picture_h264.c) copies those indexed reference fields and current POCs into its picture descriptor; the [Nouveau VP3 helper](https://gitlab.freedesktop.org/mesa/mesa/-/blob/96cb43121031992b85767f9c1be8f3f48e22b1d2/src/gallium/drivers/nouveau/nouveau_vp3_video_vp.c) serializes the descriptor's occupied entries in order.

This is a **static source-chain inference**, combined with a separate software decoder observation, not an observed FFmpeg VA-API call. It identifies a plausible alternative to the original oldest-first/relative-POC CPU fixture model. It does not prove that FFmpeg's short-term state remains identical in hardware mode, that the observed picture POCs have the required field semantics in every stream, or that macOS's proprietary NVIDIA provider uses this Linux interface. The Mesa reference was extracted from the pinned open-source 26.2.4 archive and executed on CPU; no VA-API or GPU command was issued.

For the five retained P pictures, [profiles.cpp](../bridge/experiments/video_dpb_profiles/profiles.cpp) constructs four combinations: oldest/newest reference order crossed with base POC 0/65536. Each 756-byte project proposal is checked byte-for-byte against the pinned Mesa helper. All 20 comparisons passed with UBSan on the iMac; the oldest-first/base-zero blocks match the earlier predictive fixture exactly. The arm64 MacBook reproduced all 20 hashes under ASan/UBSan with checked source and reference transfer. [iMac receipt](video-dpb-profiles-validation.json) · [MacBook receipt](video-dpb-profiles-mac-validation.json).

For P2–P5, reversing reference order changes 8–10 bytes; changing only the POC base changes six bytes. P1 has one reference, so reversal changes none, while its POC base changes four bytes. Those are byte counts, **not** performance or correctness scores. POC and ordering can have related semantics, so neither profile is established as correct for real NVIDIA hardware. The observed software reference set and output pixels are documented separately in [VIDEO_DPB_OBSERVATION.md](VIDEO_DPB_OBSERVATION.md). All outputs remain CPU-only proposals: **do not submit them to a GPU**. The older narrow adapter is unchanged.

## Reproduction

Prepare the locally extracted, hash-pinned Mesa helper as in [VIDEO_VP_PICTURE.md](VIDEO_VP_PICTURE.md), and retain the predictive and software observation results. Output and remote directories must be new. The private Mesa-generated helper is transferred only to the authorized test machine and is not distributed by this repository.

```sh
E=bridge/experiments/video_dpb_profiles
python3 "$E/validate.py" --mesa /path/to/mesa-vp-result \
  --predictive /path/to/predictive-result --observation /path/to/dpb-observation \
  --out /path/to/new-local-result
python3 "$E/validate_mac.py" --mesa /path/to/mesa-vp-result \
  --local /path/to/new-local-result --host SSH_ALIAS \
  --remote-dir /path/to/new/remote-result --out /path/to/new-mac-result
```

Next, independently establish a valid macOS transport, real surface lifetimes and the hardware-side parameter contract; only then compare decoded frames. No system component or OCLP was modified.
