# CPU-only planning for H.264 reference and intermediate buffers

The experimental [layout planner](../bridge/experiments/video_bsp_staging/VideoLayout.cpp)
calculates **relative sizes and offsets** using the pinned Mesa/Nouveau VP3
formulas for H.264. It checks arithmetic, an explicit caller-supplied budget,
the 32-bit source-field range and intermediate-ring underflow. A rejected
request leaves the previous result untouched. It creates no GPU address,
buffer, channel or command.

For the retained 320 × 240 fixture, the SPS reports a maximum of two reference
frames. If that value is used as Mesa's decoder configuration, the modeled
initial reference stride is 122,880 bytes, the reference allocation including
temporary storage is 675,840 bytes, and each of the two initial intermediate
buffers is 4,194,304 bytes. Adding those and two initial 1 MiB BSP buffers gives
11,161,600 bytes. These are **model calculations**, not measured GTX VRAM use,
available-memory checks or a hardware capacity claim.

The initial estimate excludes other allocations and can grow when later
bitstreams require larger BSP or intermediate buffers. It does not account for
transient reallocations, output surfaces, page alignment, driver overhead,
other applications or the actual macOS memory contract. The offsets describe
Mesa's internal reference layout, not established Core Video plane offsets.
A successful budget check does not authorize allocation or submission.

## Evidence

The [validator](../bridge/experiments/video_bsp_staging/validate_layout.py)
verifies the exact Mesa archive and two source members, compiles the selected
unchanged Mesa offset and intermediate-size helpers into a local CPU oracle,
and compares **49,152 values across 4,096 configurations**. The reference
wrapper uses an independently modeled power-of-two alignment operation and
selected source statements; it is not the full Mesa decoder. Tests include
budget refusals, invalid bounds and a ring-underflow case. The preserved
fixture's six header extractions and staged bytes also pass their FFmpeg
reference comparison with the planner connected. [Layout receipt](video-reference-layout-validation.json)
· [fixture regression](video-reference-layout-fixture-validation.json).

The same source, basic planner checks and six fixture samples pass ASan/UBSan
on the MacBook; source and fixture transfer hashes and output hashes are
checked against the iMac. [MacBook receipt](video-reference-layout-asan-validation.json).
This is CPU validation on two hosts, not a GTX video-engine test. The Mesa
reference is generated locally with its original MIT notice and is not
distributed in this repository.

## Reproduction

With the separately obtained pinned Mesa archive and extracted tree, use a
fresh output directory:

```sh
E=bridge/experiments/video_bsp_staging
python3 "$E/validate_layout.py" --archive /path/to/mesa-26.2.4.tar.xz \
  --tree /path/to/mesa-26.2.4 --out /path/to/new-layout-results
```

For the fixture and MacBook sanitizer regressions, use the procedures in
[VIDEO_BSP_BASELINE.md](VIDEO_BSP_BASELINE.md) with new output directories.
VideoToolbox integration still requires qualified picture/reference state,
macOS-owned resources, a video channel and independently checked hardware
output. No system driver, OCLP, firmware or GPU engine is modified here.
