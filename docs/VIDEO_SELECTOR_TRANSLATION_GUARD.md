# Why the historical video selectors cannot be truncated

The historical Sierra NVIDIA video provider contains calls to several selectors
in the `0x100`–`0x10c` table. A possible but **unqualified** proposal would be to subtract
`0x100` and call the same low index in the current video-context table. The
pinned on-disk tables show that this is not a safe translation:

| Historical selector | Historical method and descriptor | Low index | Current table entry and descriptor |
| --- | --- | --- | --- |
| `0x105` | `acquire_channel`; flags 0, counts 1 and 2 | 5 | `finish_fence_event`; flags 0, counts 1 and 0 |
| `0x101` | `set_source_size`; flags 4, counts 0 and variable | 1 | `set_client_info`; flags 4, counts 0 and variable |

The first pair differs in both the named operation and the recorded output
count. The second pair has matching raw flags and counts but different named
operations: **descriptor shape alone does not establish semantic equivalence**.
The current table's index 6 has a null member pointer, and indices 8–12 have no
entry in the inspected eight-entry table. Selector 6 has a separate special
path in the kernel analysis, so the null table entry is not a prediction of
its live result.

These are static comparisons against exact pinned files, not an observation of
live dispatch. The [conditional kernel analysis](VIDEO_SELECTOR_PATH.md)
predicts rejection of the original `0x105` only under its listed assumptions;
it does not cover all possible routes. The comparison does not prove that no
other implementation or deliberate adapter could exist. A usable adapter needs
independent semantics, resources, ownership, lifetime and kernel transport;
**the supplied checker authorizes no selector mapping and issues no calls**.
No decoded hardware frame, driver change or speed improvement is established.

## Evidence and reproduction

The auditor independently checks the full historical and current file hashes,
the old 13-entry method table and symbol identities, and all eight current
48-byte descriptor hashes and fields against the retained audits. It compares
only the raw fields, preserving their historical ABI qualification. The
[sanitized result](video-selector-low-index-validation.json) records all eight
low-index comparisons and the five higher historical selectors without vendor
binary data. Prior evidence is explained in [the Sierra dispatch comparison](VIDEO_PROVIDER_DISPATCH.md)
and [the current method contract](VIDEO_METHOD_CONTRACT.md).

Use the retained private Sierra GeForce image and the exact installed current
IOAccelerator profile; a changed binary, receipt or existing output is refused.
No GPU, IOKit connection or provider program is opened by this audit.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
python3 bridge/experiments/video_selector_translation_guard/audit.py \
 --legacy-geforce "$LAB/results/video-sierra-kernel-contract-20261027-01/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce" \
 --current-ioaccel /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2 \
 --out "$LAB/results/video-selector-low-index-new.json"
python3 -m unittest discover -s tests -p 'test_video_selector*.py'
```
