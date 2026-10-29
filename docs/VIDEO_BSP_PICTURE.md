# CPU preparation of H.264 BSP picture parameters

An experimental `prepare_h264_bsp_picture` function now combines the existing
[stream staging](VIDEO_BSP_STAGING.md) with a 124-byte BSP picture block and
flags derived from Mesa 26.2.4. The caller supplies dimensions, slice count,
SPS/PPS-derived fields and picture fields; this code does not parse or validate
an H.264 bitstream. On a refused input it preserves the caller's previous
output and flags. Explicit dimension and slice-count bounds are project bounds,
not measured hardware capabilities.

**This buffer remains incomplete and must not be submitted to the GPU.** The
implementation does not supply the VP picture block, reference surfaces,
memory mappings, a video channel, commands, synchronization or a macOS driver
transport. The Mesa-derived values are a CPU research artifact; their
compatibility with the installed NVIDIA driver and actual hardware remains
unproved. This does not claim video decoding, Metal support or a speedup.

## Validation

The [validator](../bridge/experiments/video_bsp_staging/validate_picture.py)
checks the exact Mesa archive and source member and compiles Mesa's unchanged
H.264 BSP picture helper into a local CPU-only reference with minimal test
types. It compares **4,096 synthetic inputs**, including selected boundary
values, against the new implementation: **507,904 picture bytes** and the
corresponding flags match. The watchdog bit added by Mesa's separate `bsp_end`
is checked separately; that function is not executed by this reference.
The synthetic cases are not proof that each combination is a valid H.264
picture. Tests under UndefinedBehaviorSanitizer also reject invalid dimensions,
slice counts, selected out-of-range fields, null input and oversized streams,
and check that rejected calls do not change either output.

The stream-only regression was also repeated on the retained 43,898-byte
Annex-B fixture across six chunkings. [Picture receipt](video-bsp-picture-validation.json)
· [stream regression receipt](video-bsp-staging-regression-validation.json).
All comparisons execute on CPU; no NVIDIA or Apple binary, GPU video engine,
system driver or OCLP component is modified by the tests.

## Reproduction

Obtain the separately pinned Mesa source and archive described in the
[stream staging report](VIDEO_BSP_STAGING.md). The validator requires their
exact hashes, retains Mesa's original MIT notice in its locally generated
reference, and requires a fresh output directory:

```sh
E=bridge/experiments/video_bsp_staging
python3 "$E/validate_picture.py" --archive /path/to/mesa-26.2.4.tar.xz \
  --source /path/to/mesa-26.2.4/src/gallium/drivers/nouveau/nouveau_vp3_video_bsp.c \
  --out /path/to/new-picture-results
```

A later [bounded baseline-header extractor](VIDEO_BSP_BASELINE.md) obtains
selected fields from a real, externally delimited test fixture. Reference
surfaces and the separate macOS video channel and address-space contract still
need qualification before any hardware submission can be tested.
