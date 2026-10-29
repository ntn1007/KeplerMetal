# Sierra codec-property survey and NVIDIA startup comparison

A full literal search of the retained macOS 10.12.6 Combo update payload
examined **70,898 regular files** among 105,031 archive records. Fourteen
members contain `IOGVACodec` in one of the three searched encodings: five AMD
graphics binaries, six Intel graphics plists and three Apple media frameworks.
No matching path is NVIDIA-labelled. The result is bounded to regular members
of this payload, ASCII and UTF-16 byte sequences; nested compression and
dynamically generated or indirect keys remain unexamined. A missing literal is
not proof that a runtime producer cannot exist.

A separate static comparison examined the earlier Sierra `GeForce` binary whose
hash matches the payload member. Its `nvAccelerator::start` routine loads the
key `NVDA,mm-version`, the value `3` and width `32`, then calls a virtual slot.
The matching vtable relocation names
`IORegistryEntry::setProperty(char const*, unsigned long long, unsigned int)`.
This demonstrates a second **static property-publication path** in the
historical NVIDIA code, but it is a different property from `IOGVACodec`.
Neither the runtime vtable target nor a runtime write was observed, and no
NVIDIA codec value follows from it. The previously examined AMD `VCE` string
is not a NVIDIA value.

The survey records the CPIO SHA-256
`09314e94e288a088ac761b61e6fe7a0bac2967dc93478b8454b7c912d7a15834`.
A separate streaming pass over all **348** pbzx chunks of the retained package
payload produces the same decoded length and SHA-256 without writing an
extracted archive. The cross-check independently reads the selected GeForce
member and matches its SHA-256 to the previous Sierra driver comparison, and
checks six Intel plist control values. The package signature was **not**
rechecked in this survey. [Survey](video-gva-sierra-survey-validation.json),
[payload identity](video-gva-sierra-payload-identity.json), and
[cross-check](video-gva-sierra-survey-crosscheck.json) are published without
vendor binaries.

The NVIDIA comparison binds the binary, instruction window, vtable relocation
and REA/Ghidra 12.1.4 dossier
`ev_7d3ad8f078aa03b6c531dec6bc08bc50c0b1b8f228ecf900c9c70c28d4bdf795`;
see the [audit receipt](video-gva-nvidia-start-comparison.json). Four synthetic
tests check the archive scanner and pbzx identity logic. No vendor driver or
GPU was executed and no system component, OCLP or firmware was changed.
Hardware video remains unproved and the safe source of an NVIDIA codec value
is unresolved.

## Reproduction

Use the retained Sierra archive, its compressed package `Payload`, the private
previously qualified GeForce binary and retained REA bundle. All output paths
must be fresh. The survey computes the archive digest; the final cross-check
requires the pinned Sierra digest and matching compressed-payload digest.

```sh
E=bridge/experiments/video_gva_archive_survey
R='/path/to/nvidia-880m-lab/bridge/results'
CPIO='/path/to/sierra/extract/sierra-payload.cpio'
PAYLOAD='/path/to/sierra/extract/macOSUpdCombo10.12.6.pkg/Payload'
python3 "$E/sierra_survey.py" --archive "$CPIO" --out "$R/sierra-survey-new.json"
python3 "$E/payload_identity.py" --payload "$PAYLOAD" --survey "$R/sierra-survey-new.json" --out "$R/sierra-pbzx-new.json"
python3 "$E/audit_nvda.py" --binary /private/path/GeForce --survey "$R/sierra-survey-new.json" \
  --rea /private/path/REA-nvidia-sierra.private.json --amd docs/video-gva-amd-dynamic-property-validation.json --out "$R/sierra-nvda-new.json"
python3 "$E/verify_sierra.py" --archive "$CPIO" --survey "$R/sierra-survey-new.json" \
  --payload-receipt "$R/sierra-pbzx-new.json" --nvidia-audit "$R/sierra-nvda-new.json" --out "$R/sierra-check-new.json"
python3 -m unittest discover -s tests -p 'test_video_gva_archive_survey.py' -v
python3 -m unittest discover -s tests -p 'test_video_gva_pbzx_identity.py' -v
```

The REA bundle is pinned; a fresh analysis can corroborate it independently but
may have a different digest. The private binaries and bundles are not published.
