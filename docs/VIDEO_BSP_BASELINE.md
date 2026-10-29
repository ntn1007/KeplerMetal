# Bounded H.264 baseline headers for BSP preparation

The experimental [extractor](../bridge/experiments/video_bsp_staging/H264Baseline.cpp)
reads separate SPS/PPS NAL units and one **externally delimited** AVCC access
unit, extracts selected fields for the existing BSP picture builder, and
converts the sample NALs to Annex-B bytes. It checks consistency across the
observed slice prefixes and rejects several unsupported inputs without changing
the previous result.

This is a deliberately limited header extractor, **not a complete H.264
parser or bitstream validator**. Its current accepted subset includes baseline
profile 66, progressive uncropped pictures, picture-order type 0, I/P slices,
no slice groups, no PPS extension, no redundant picture count and a zero
default L1 count. It requires increasing slice starts with matching selected
picture fields. It skips VUI and SEI contents and does not parse the complete
slice header or payload, validate all H.264 syntax, discover access-unit
boundaries, or manage decoded references. A malformed or unsupported stream
may therefore be rejected, and acceptance is not proof of full validity.

The extractor now also reports the SPS maximum-reference count to an
experimental [relative layout planner](VIDEO_REFERENCE_LAYOUT.md). This is a
model of initial Mesa allocations, not a measurement on the GTX.

**The resulting BSP buffer remains incomplete and must not be submitted to a
GPU.** A later [CPU-only VP model for one restricted IDR](VIDEO_IDR_VP.md)
does not provide actual reference surfaces, mappings, video channels, commands
or synchronization. No hardware decoding or performance improvement is claimed.

## Evidence

On the retained six-frame fixture, FFmpeg 9.0.2's `trace_headers` ran on the
MacBook in stream-copy mode. Its binary and input hashes were checked before
and after the run. On the iMac, the extractor's selected fields matched the
independent trace for **six pictures and twelve slice headers**; each picture
had two slices starting at macroblocks 0 and 150. The staged BSP picture
blocks, flags and preserved sample bytes were checked against independently
constructed expectations from those fields. This comparison does not decode
the images or prove hardware compatibility. A modified trace was rejected even
after its hash was updated. [Current header and layout receipt](video-reference-layout-fixture-validation.json)
· [FFmpeg capture receipt](video-bsp-ffmpeg-trace-validation.json).

Synthetic malformed, truncated, unsupported and inconsistent inputs were
tested with UndefinedBehaviorSanitizer on the iMac. The same source and six
real fixture samples were copied to the MacBook over authenticated SSH, with
hashes checked at both ends before and after. AddressSanitizer and
UndefinedBehaviorSanitizer passed there; its six staged output SHA-256 hashes
matched those from the iMac. [Current MacBook receipt](video-reference-layout-asan-validation.json).
This was CPU work on arm64, not a test of the GTX. On the iMac, an ASan test
and a separately compiled empty ASan control both exited with signal 4; the
cause was not established, so iMac ASan coverage is unavailable.

## Reproduction

The fixture and raw FFmpeg trace are private local inputs. With a matching
fixture on an SSH-accessible arm64 reference host, capture a new trace using
explicit paths, then validate on the iMac. `capture_trace.py` uses stream copy
and requires the previously qualified Annex-B fixture hash; it does not write
files on the reference host.

```sh
E=bridge/experiments/video_bsp_staging
python3 "$E/capture_trace.py" --host YOUR_SSH_ALIAS \
  --remote-ffmpeg /absolute/path/to/ffmpeg --remote-fixture /absolute/path/to/fixture-annexb.h264 \
  --out /path/to/new-reference
python3 "$E/validate_baseline.py" --fixture /path/to/avcc-fixture-directory \
  --reference /path/to/new-reference --out /path/to/new-validation
python3 "$E/asan_mac.py" --host YOUR_SSH_ALIAS --remote-dir /absolute/new/remote-directory \
  --fixture /path/to/avcc-fixture-directory --baseline /path/to/new-validation \
  --out /path/to/new-sanitizer-results
```

All output directories must be fresh. Further work must qualify complete
picture metadata and reference ownership, then the separate macOS video
transport; these tests do not authorize an unqualified private GPU command.
