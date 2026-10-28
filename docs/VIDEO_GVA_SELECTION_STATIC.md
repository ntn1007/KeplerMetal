# AppleGVA candidate selection: bounded static follow-up

This analysis narrows the next observation target after the [first-pixel-buffer witness](VIDEO_NATIVE_START.md). It does not observe a candidate being selected or explain the `-12913` hardware-decoder failure. Hardware decoding and the full GPU objective remain unproved.

On the captured AppleGVA 10.0.20 image UUID `ca5414f369373c059ea2d82b35afd4f0`, two function regions are independently checked against the currently readable shared-cache bytes: 1,136 bytes at image offset 146348 and 213 bytes at offset 151999. Their SHA-256 values are in the [validation record](video-gva-selection-static-validation.json). The capture's UUID is checked; the cache byte comparison alone is not a fresh proof of the loaded image UUID or runtime instruction execution.

The 213-byte region passes an IOService-plane `board-id` query with options 1 to a statically mapped `IORegistryEntrySearchCFProperty` stub, and has statically mapped CFData byte/length calls. In the 1,136-byte region, three equality checks compare the returned string with three model identifiers. The iMac's board identifier observed separately with `ioreg` is different from all three. That separate observation does **not** establish the value returned to AppleGVA in the test process.

For the particular control-flow route that reaches all three comparisons without a match, instructions at image offsets 146992 and 146995 test a candidate pointer. A null value branches to 147429; a non-null value proceeds to a call at 147011 targeting image offset 151776. This is a conditional static finding: earlier alternatives, including another input route and forced selections, exist. The candidate pointer's meaning, its actual value, the downstream call's complete behavior, and whether any of this code ran in the historical decoder failure remain unknown. No absence of a provider is inferred from the pointer test.

The source-only auditor checks original capture metadata, captured and current-cache region hashes, pinned static stub maps, relative branch/call targets and the queried constants. It reports offsets and selected model identifiers, never vendor instructions. Altered-region and altered-map controls are refused; three portable unit tests pass. Vendor captures and REA evidence remain in the private laboratory. REA 6.4.0/Ghidra 12.1.4 examined derived ELF containers; the decompiler warns about bad instruction data and external targets, so this finding was checked against the original captured instructions and recorded stub mappings. REA addresses for these ELF containers are rebased by `0x100000` compared with the original unslid cache addresses; published offsets refer to the original image, not the synthetic containers.

No video engine was submitted work, no system component or OCLP was modified and no benchmark was run. The next useful experiment is a strictly scoped, ABI-qualified observer of the existing public registry query and candidate outcome, with controls and exact current-profile checks. It must first establish that the relevant code is reached; do not manufacture a registry property or call private factories to turn this static route into a claimed fix.

## Reproduction with existing private evidence

The exact retained captures and mapping inputs are required; see [dependency recovery](DEPENDENCIES.md). The existing `map_video_stub_targets.py` can reconstruct each static map from its corresponding captured analysis. Its source hash and the analysis inputs must match the pinned records. Use fresh output paths.

```sh
python3 bridge/tools/video_gva_selection_static.py \
  --cache "$CACHE" \
  --inner "$LAB/results/video-gva-session-enumeration-inner-20261018" \
  --board "$LAB/results/video-gva-session-selection-preference-20261018" \
  --inner-map "$LAB/results/video-session-inner-stubs-20261027-01.json" \
  --board-map "$LAB/results/video-session-board-stubs-20261028-01.json" \
  --host-board "$BOARD_ID" --out "$LAB/results/video-gva-selection-new.json"
python3 -m unittest discover -s tests -p test_video_gva_selection_static.py -v
```

`BOARD_ID` is an explicit separately observed input, not a value acquired by or attributed to AppleGVA. No proprietary Apple or NVIDIA program is included in this repository.
