# AppleGVA video constructor dispatch: narrowed candidate values

The previously recorded AppleGVA stack includes return offset **115492**. In
the pinned on-disk AppleGVA image, the instruction immediately before that
offset calls an internal target at **233054** from a selector branch. Independent
decoding of the 15 signed, four-byte jump-table entries shows that selector
values **2 and 9** share the branch containing that call. REA/Ghidra recovered
the same non-default case targets from the separately verified analysis object.

If the recorded frame is accurate, the live code follows this same pinned
entry flow, and the call was reached through the checked jump table, the
recorded constructor branch is consistent with one of those two values. The
actual register was **not recorded**. The available observations do not prove
which value occurred, that it is a public codec ID, or that every path into the
instruction is covered. The captured stack is not complete, and loaded bytes
were not verified for every frame. This is a conditional inference, not a
runtime selector measurement or a decoder implementation.

The [previous cohort](VIDEO_GVA_PROPERTY.md) has nine matching stack records
from three policy conditions. Those hardware requests used process-local
`IOGVACodec` and board-policy counterfactuals and all produced zero hardware
images. Their existing 14-process auditor was rerun on the original captures;
the separate stack mapper was rerun against the current cache and a recorded
host. No vendor program or GPU work was executed for this new analysis.

The extracted 719-byte region has SHA-256
`cb8e85197a4b37270ced86a070fecb85bb61ea56aa98892996658a304544db0c`.
The ELF analysis container has SHA-256
`5ebac1c972a7b134e8676aa0bc20c2a51fdc8418145daea30e9a526cf2f8b7e5`;
the audit verifies its source section byte-for-byte. REA 6.4.0 / Ghidra 12.1.4
recovered a 467-byte function body from that container, with inline table data
outside the body. Evidence ID is
`ev_415b2e7d3c80855d44d12dfda5e5c80d10b1e10779b86551758f41664a4570ef`.
Its recovered address is rebased by `0x100000`; offsets here refer to the
original AppleGVA image. Pseudocode and captures stay in the private lab.

An independent static stub map associates the allocator call on this branch
with C++ nothrow `operator new`. Its **runtime binding has not been proved**.
A possible next experiment is a narrowly scoped, ABI-calibrated own-process
observer that validates the live region and records the selector register at
that call without changing the allocation. Interposition coverage, earlier
resolution, register preservation and failure/cleanup must be qualified before
any result is interpreted. No private function should be called directly.

[Sanitized audit](video-gva-dispatch-validation.json). No macOS component,
driver, OCLP or firmware was modified. No video engine submission, decoded
hardware image or performance improvement is claimed.

## Re-audit

Requires the exact retained private lab, the current cache/profile and the
previous property cohort. Fresh output paths are mandatory. Run the previous
[property cohort auditor](VIDEO_GVA_PROPERTY.md) and
[`stack_map.py`](../bridge/experiments/video_gva_support_overlay/stack_map.py)
first. The stub mapper is `bridge/tools/map_video_stub_targets.py`; it reads
the cache and never executes vendor instructions. No private files are
distributed.

```bash
R="$KP_LAB/bridge/results"
python3 bridge/experiments/video_gva_dispatch/audit.py \
  --region "$R/video-gva-provider-session-20261018/function-region.private.bin" \
  --metadata "$R/video-gva-provider-session-20261018/metadata.json" \
  --object "$R/video-gva-provider-session-analysis-20261018/region-00/analysis.private.o" \
  --rea "$R/video-gva-session-dispatch-rea-20261028-01.private.json" \
  --stack-map "$R/gva-overlay-stack-map-reaudit-20261028-01.json" \
  --cohort-audit "$R/gva-property-reaudit-20261028-02.json" \
  --stub-map "$R/gva-session-dispatch-stubs-20261028-01.json" \
  --out "$R/gva-dispatch-stack-audit-new.json"
python3 -m unittest discover -s tests -p test_video_gva_dispatch.py -v
```

The fixed hashes intentionally refuse a regenerated REA bundle or changed
profile; a new capture requires separate qualification, not silent repinning.
