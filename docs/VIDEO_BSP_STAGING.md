# CPU-only H.264 stream staging for Kepler video research

The [experimental C++ component](../bridge/experiments/video_bsp_staging/H264Stream.cpp)
constructs the stream portion of the buffer layout described by Mesa 26.2.4's
Nouveau VP3 code. It concatenates caller-provided byte chunks at offset
`0x700`, adds the two H.264 end markers and zero words, and writes the stream
length and flag at offsets `0x100` and `0x110`. It zeroes the rest of its
owned vector. It neither parses H.264 nor constructs the picture parameters.

**The buffer is incomplete and must not be sent to the GPU.** It contains no
qualified picture descriptor, GPU addresses, channel bindings or submission
commands. The code is not yet wired into the main runtime. Neither a compatible
macOS video transport nor hardware decoding is established. A real decoder
also needs per-picture boundaries and metadata, reference-picture handling,
resource ownership, synchronization and the other BSP/VP/PPP stages.

## Validation

The [local validation](video-bsp-staging-validation.json) checks an exact Mesa
archive and source member, compiles Mesa's unchanged `bsp_begin` and `bsp_next`
helpers with a minimal CPU-only fixture, and compares the whole staged vector
for six chunkings of the retained 43,898-byte Annex-B test stream. All six
match byte-for-byte. That input contains multiple frames; its use here checks
byte preservation and chunking, not valid per-frame decoder submission.

The reference wrapper writes the H.264 trailer and stream flag independently;
it does **not** compile or test Mesa's codec-specific `bsp_end` or picture
parameter generation. Unit checks under UndefinedBehaviorSanitizer cover
segmented and empty input, null pointers, the conservative 24-bit length
boundary including the trailer, overflow refusal and preserving the previous
output on refusal. The 24-bit bound follows a Mesa source comment and is a
project safety limit, not a measured macOS or hardware maximum. No GPU or
vendor code is executed by this validation.

The Mesa source is copyright 2011–2013 Maarten Lankhorst and is MIT licensed;
the reference is generated locally from the verified archive with its original
notice. Neither that generated file nor the private test stream is published.

## Reproduction

The small CPU test needs only the public source and a C++17 compiler:

```sh
E=bridge/experiments/video_bsp_staging
xcrun clang++ -std=c++17 -O1 -g -fsanitize=undefined \
  "$E/H264Stream.cpp" "$E/test.cpp" -o /tmp/kepler-bsp-staging-test
/tmp/kepler-bsp-staging-test
```

For the Mesa comparison, obtain the separately pinned Mesa 26.2.4 archive and
source and an exact copy of the previously qualified Annex-B fixture. The
validator refuses changed inputs and writes into a new directory:

```sh
E=bridge/experiments/video_bsp_staging
python3 "$E/validate.py" --archive /path/to/mesa-26.2.4.tar.xz \
  --source /path/to/mesa-26.2.4/src/gallium/drivers/nouveau/nouveau_vp3_video_bsp.c \
  --fixture /path/to/fixture-annexb.h264 --out /path/to/new-results
```

The next implementation boundary is the H.264 picture descriptor and frame
ownership; in parallel, the macOS channel and address-space contract remains
unqualified. Neither should be inferred from this CPU staging comparison.
