# H.264 one-reference POC type 2 preparation

The CPU-only baseline extractor and VP picture proposal model now accept a restricted progressive H.264 case with one short-term reference and picture-order-count type 2. Slice types 5 and 7 are normalized to their equivalent P and I types, while values above 9 and unsupported slice kinds remain refused. Type 2 has no `pic_order_cnt_lsb` field; the extractor represents that absence as zero. For the accepted reference-only P sequence without frame-number wrap, the proposal derives both picture orders as twice the frame number. The existing type 0 / two-reference case remains supported.

This is **not a decoder**. Reference completion and target identities are simulated in the fixture harness. Neither a GPU surface nor buffer lifetime, video transport, hardware decoding, encoding, or performance is established. Proposals must not be sent to a GPU. The parser remains a bounded header extractor, not a complete H.264 syntax validator. POC type 2 wrap, non-reference P pictures, long-term references, modified reference lists and adaptive marking remain outside this path. The model continues to refuse unsupported inputs.

## Evidence and limits

An arm64 FFmpeg 9.0.2 / libx264-generated six-frame 320×240 fixture uses a baseline progressive profile, one reference, POC type 2, two slices per frame, one IDR and five P pictures. Its 12 slice headers match the pinned `trace_headers` output. On the iMac, five independently constructed 756-byte VP proposals match the retained Mesa 26.2.4 reference helper byte for byte. Synthetic tests cover normalized slice types, type 2 headers, out-of-range types, a bad reference, a frame-number wrap and output preservation on refusal. The iMac run uses UBSan.

A separate arm64 run transfers only the exact sources and fixture inputs, checks SHA-256 on both ends before and after, and passes ASan/UBSan; all five proposal hashes match the iMac. FFmpeg's software decoder also produces six frames with no reported decode errors. Its 12 debug slice snapshots show the immediately preceding frame as the single short-term reference, matching the proposal values. Software frame hashes match the saved NV12 output after planar conversion; both software references use the **same FFmpeg binary**, so they are not independent decoders. These software observations do not establish NVIDIA engine behavior. The old type 0/two-reference fixture was rerun and its five output hashes match the earlier archived results.

- [iMac receipt](video-one-reference-validation.json)
- [MacBook sanitizer receipt](video-one-reference-mac-validation.json)
- [Previous-fixture regression](video-one-reference-legacy-validation.json)
- [Software reference-list observation](video-one-reference-dpb-validation.json)

An initial Mesa comparison failed because the new harness swapped the slice count and maximum-reference fields in its oracle call. That failed output remains in the lab; the corrected independent helper comparison was rerun. The historical reports and proofs were not modified. The exact original binaries and private input data are not published.

## Reproduction

The retained test fixture was generated using FFmpeg SHA-256 `7f6028378534aa10a2dfa07d807ddcc0d18c869bf5c2f64c89efcc18ee88c4ee` on arm64 with:

```sh
ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc2=size=320x240:rate=2 \
  -frames:v 6 -c:v libx264 -profile:v baseline -pix_fmt yuv420p -refs 1 \
  -bf 0 -g 30 -x264-params scenecut=0:keyint=30:min-keyint=30:slices=2 \
  -f h264 fixture.h264
ffprobe -v error -select_streams v:0 -show_entries packet=pos,size -of json fixture.h264 > packets.json
ffmpeg -hide_banner -loglevel info -i fixture.h264 -c:v copy -bsf:v trace_headers -f null - 2>trace.txt
ffmpeg -v error -i fixture.h264 -pix_fmt nv12 -f rawvideo software.nv12
```

Exact fixture and trace hashes are pinned by the checker; differences in ffmpeg, x264, logging or encoder settings require a separately qualified fixture rather than a silent repin. With the retained fixture and previously generated local Mesa VP reference, use fresh output directories:

```sh
E=bridge/experiments/video_bsp_staging
python3 "$E/validate_one_reference.py" --fixture /path/to/fixture-dir \
  --mesa /path/to/mesa-vp-reference.private.c --out /path/to/new-result
python3 "$E/validate_one_reference_mac.py" --local /path/to/new-result \
  --host SSH_ALIAS --remote-dir /absolute/new/remote-directory --out /path/to/new-mac-result
python3 "$E/validate_one_reference_legacy.py" --fixture /path/to/old-fixture \
  --baseline /path/to/old-baseline --prior /path/to/old-predictive-validation.json \
  --local /path/to/new-result --out /path/to/new-legacy-result
python3 bridge/experiments/video_dpb_observation/one_ref.py --host SSH_ALIAS \
  --remote-ffmpeg /absolute/path/to/ffmpeg --remote-fixture /absolute/path/to/fixture.h264 \
  --predictive /path/to/new-result --reference-nv12 /path/to/software.nv12 \
  --out /path/to/new-dpb-result
```

The next required step is a separately qualified real resource/transport contract and hardware image comparison. The new CPU model alone does not authorize a private NVIDIA request.
