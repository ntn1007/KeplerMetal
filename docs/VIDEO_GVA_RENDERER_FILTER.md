# A second filter on the observed AppleGVA renderer entry

The pinned AppleGVA selection routine does more than test the node's `0x463`
byte. In its **selection-flag-zero** path, a node which passes the `0x461` and
`0x463` checks is then classified using the 32-bit field at offset `0x428`.
The filter accepts two finite groups of numeric values:

| Group | Accepted 32-bit values |
| --- | --- |
| First | `0x01080001`, `0x01080002`, `0x01080004`, `0x01080008`, `0x01080010`, `0x01080020`, `0x01080080` |
| Second | `0x01020000`, `0x01020002`, `0x01020004` |

At two stopped list snapshots in each of the two earlier synthetic-property
runs, the sole observed node had field **`0x01040008`**, flags `1,0,0,1` and a
null next link. The observed selection flag was zero and the model classifies
that field into neither group. The subsequent enumeration count was zero and
the hardware-required request returned `-12913`, with no frames. The probe-off
control had the same numeric field and flags `1,0,0,0`.

**Interpretation:** if the one observed entry and the selection conditions
remain unchanged after the debugger resumes, and normal pinned control flow
applies, the renderer classification would exclude the entry even after the
synthetic property makes its flag nonzero. With no accepted candidates, the
inspected path leaves its output empty. This is a testable explanation for why
the earlier counterfactual did not populate the list. The actual classification
branch was not traced, object lifetime is not proved, and the stopped snapshot
does not exclude subsequent mutation. The full VideoToolbox failure cause is
not established; changing the numeric field or bypassing the filter would not
by itself prove the decoder or provider compatible.

The node field matches the separately recorded `IOVARendererID` **numerically**;
that match does not prove object identity or the meaning of Apple's categories.
The synthetic string is not an NVIDIA configuration value. No new GPU or vendor
code was executed for this static audit, and no performance improvement or
hardware decoding is claimed.

## Evidence and reproducibility

The static source is the previously captured 1,136-byte AppleGVA region with
SHA-256 `4c07b6daa5d9e4449c3f77192951ffa230915193befe87cbbf443e25226fa564`
and image UUID `ca5414f369373c059ea2d82b35afd4f0`. Image-relative offsets
`0x23ca9`–`0x23d3a` cover the flag checks, numeric classifier and empty-candidate
branch. An independently generated private ELF container preserved those bytes
and was analyzed with REA/Ghidra 12.1.4: evidence
`ev_85c3930ac61c44d71934e0ce8ef511410b4c33d4e99bd4dea11c7cfdd347d8d1`.
Ghidra mapped the section at `0x123bac`; subtract `0x100000` for the original
image-relative offsets. The wrapper is a derived analysis artifact, not an
AppleGVA executable or a complete image: external references, types and runtime
behavior are not established by its decompilation.

The [sanitized audit](video-gva-renderer-filter-validation.json) checks the
capture and instruction-window digests, binds three prior terminal run receipts
and their debugger logs, and models the unsigned comparison and masks. Unit
tests cover all bits in both masks, their boundaries and the observed value.
They test the model, not execution of Apple's code. The preceding runtime
experiment and its controls are documented [here](VIDEO_GVA_CODEC_COUNTERFACTUAL.md).

```bash
R='/path/to/nvidia-880m-lab/bridge/results'
python3 bridge/experiments/video_gva_renderer_filter/audit.py \
  --region "$R/video-gva-session-enumeration-inner-20261018/function-region.private.bin" \
  --metadata "$R/video-gva-session-enumeration-inner-20261018/metadata.json" \
  --prior-audit "$R/gva-codec-probe-audit-20261029-01.json" \
  --runs "$R/gva-codec-probe-off-20261029-01" "$R/gva-codec-probe-synthetic-20261029-01" "$R/gva-codec-probe-synthetic-20261029-02" \
  --out "$R/gva-renderer-filter-audit-new.json"
python3 -m unittest discover -s tests -p 'test_video_gva_renderer_filter.py'
```

A discriminating next step is a bounded read-only witness at the actual
classification branch, with a CPU calibration, rather than assuming the stopped
entry survives unchanged. Hardware-provider compatibility would still need
separate validation.
