# Full High Sierra update survey for `IOGVACodec`

The previously retained macOS 10.13.6 Combo update payload was scanned in a
single streaming pass without extracting or executing its members. The scan
examined **54,110 regular files** among 86,095 archive records for the literal
`IOGVACodec` in ASCII, UTF-16LE and UTF-16BE. Fifteen regular members matched:

- Seven Intel/AMD graphics plists, whose decoded values match the controls in
  the [earlier NVIDIA-focused inventory](VIDEO_GVA_HIGH_SIERRA_INVENTORY.md).
- Three AMD graphics binaries, including `AMDRadeonX3000` and `AMDRadeonX4000`.
- Four Apple media framework binaries and one Apple HEVC encoder plugin.

None of the 34 previously inspected GeForce/NVDA members appears among the
matches, and none of the other matching paths is NVIDIA-labelled. A literal in
an AMD binary is a lead for further analysis, not evidence that it creates a
property or that its value applies to NVIDIA. No NVIDIA codec value was found.

This is the complete set of regular members **in this update payload**, not a
complete installation. The scan does not unpack nested compressed members,
interpret every binary encoding, or exclude a dynamically generated property.
It cannot establish whether the GTX video engine or any provider works. The
CPU-only [cross-check](video-gva-archive-survey-crosscheck.json) compares all
seven prior plist controls and the 34 previously selected NVIDIA members. The
[full receipt](video-gva-archive-survey-validation.json) contains member
names, sizes, hashes, literal counts and bounded plist values; it contains no
Apple binaries. Two synthetic tests cover chunk boundaries, three encodings,
plist decoding and malformed archives.

The source payload has SHA-256
`b48e6eaaacb86400dfc9e84ed85a8df666baa24af7ca3a632b73607a1d2f4cc6`.
Its original signed-update provenance is documented in
[VIDEO_HIGH_SIERRA_COMPARISON.md](VIDEO_HIGH_SIERRA_COMPARISON.md); this scan
checks the retained payload hash and does not repeat the signature audit. No
GPU or vendor program was executed and no system, OCLP or firmware file changed.

## Reproduction

Use the retained 5,801,167,872-byte payload and a fresh output directory. The
reader streams the archive and refuses mismatched size, digest, member count or
unsupported archive structure. It does not extract any member.

```sh
CPIO='/path/to/high-sierra-10.13.6/extract/high-sierra-payload.cpio'
R='/path/to/nvidia-880m-lab/bridge/results'
E=bridge/experiments/video_gva_archive_survey
python3 "$E/survey.py" --archive "$CPIO" --out "$R/full-survey-new.json"
python3 "$E/verify.py" --survey "$R/full-survey-new.json" \
  --prior docs/video-gva-high-sierra-inventory-validation.json --out "$R/full-survey-check-new.json"
python3 -m unittest discover -s tests -p 'test_video_gva_archive_survey.py' -v
```
