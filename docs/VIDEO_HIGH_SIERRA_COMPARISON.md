# NVIDIA video: Sierra, High Sierra and the current stack

A read-only comparison of three pinned macOS component profiles narrows the missing video-provider boundary. The High Sierra components were extracted from Apple's signed [macOS 10.13.6 Combo Update](https://support.apple.com/en-sa/106398), not installed. The package contains both `GeForceVADriver.bundle` and the matching `GeForce.kext` and `IOAcceleratorFamily2.kext`. The image checksum passed, `pkgutil` reported a signed Apple Software package with a trusted timestamp, and all three extracted bundles passed `codesign --verify --strict`. These checks establish the inspected artifacts and signatures, not their compatibility with the current machine.

| Static profile | NVIDIA `AVD_CreateAVDAccelerator` | `nvVideoContext` lookup in on-disk GeForce |
| --- | --- | --- |
| Sierra 10.12.6 Combo | 571-byte function; not the known return-14 stub | Local specialized lookup |
| High Sierra 10.13.6 Combo | **11-byte known return-14 stub**, same function hash as current | External relocation to generic `IOAccelContext2` lookup |
| Current installed component | **11-byte known return-14 stub** | External relocation to generic `IOAccelContext2` lookup |

A large file does not imply a working factory: the High Sierra provider is 1,610,624 bytes, but its named creation export has the identical 11-byte stub hash `56ab2f750b92826bbc9b12d9878950be8e7783a12315c2efcdcd169726fe8eb4`. Its static code also contains two calls with nearby selector immediate `0x105` (`0x2d3a2`, `0x2d5d9`). The bounded named direct-call graph finds no path from the stub export to `IOServiceOpen`; it does not cover all indirect entry points and does **not** establish whether those selector candidates execute or which connection they use.

The High Sierra GeForce vtable slot at `0x8c638` carries an external relocation to `IOAccelContext2::getTargetAndMethodForIndex`. In the companion on-disk IOAccelerator image, the 72-byte function at `0x6e90` checks the selector against 7 at `0x6eb3`, branches at `0x6eb6`, and returns zero at `0x6ecb` for larger indices. REA / Ghidra 12.1.4 independently corroborates this function on the pinned file (evidence ID `ev_6f121f82e16a85dcb2f4bb33adbed7918b01fe8db2e4d33241c2be64f30d958b`; private evidence retained in the lab). This is static evidence, not a trace of a running kernel. `externalMethod` fallback and other paths remain unqualified; this observation alone does not prove a live `0x105` refusal.

The [Sierra dispatch comparison](VIDEO_PROVIDER_DISPATCH.md) previously identified a specialized `0x100`–`0x10c` table and an `acquire_channel` entry. Together these observations argue against treating either an old provider copy or its remaining code as a simple drop-in decoder. They do not establish all High Sierra installations or releases, a hardware limitation, a full ABI, or a valid replacement. No vendor provider, private video selector or video engine was executed in this comparison. No macOS, OCLP, firmware or driver was modified.

The [machine-readable audit](video-high-sierra-validation.json) includes exact image hashes, UUIDs, source locations and limits. Archive SHA-256: `94c302b4633b8fa77295a6db75099e89a404a86451f279a9f47ca8f4dbfd67ac`; package SHA-256 as observed by REA: `77c717f1d71396d3e17ab7d48baacd96bde57039bd64bae45b25c60aa273f544`. The proprietary archives and extracted files remain outside this repository.

A [follow-up channel inventory](VIDEO_CHANNEL_BRANCHES.md) also checks direct calls and tail jumps across all three GeForce images; indirect reachability remains unknown.

## Reproduction

Apple's support page supplies the official download. Use an isolated directory with at least 12 GiB free; the image is 2.49 GB and its decompressed payload is approximately 5.8 GB. The following only reads and extracts files; it does not install the update. Verify the archive SHA above and the package signature before extraction. Always detach the read-only image, including if an intermediate command fails.

```sh
W=/absolute/path/to/high-sierra-lab
mkdir -p "$W/mount" "$W/extract/bundles"
curl --fail --location --output "$W/macOSUpdCombo10.13.6.dmg" \
 'https://updates.cdn-apple.com/2019/cert/041-91759-20191011-01650bca-c2ef-42de-b8a8-63c3fd7d55bc/macOSUpdCombo10.13.6.dmg'
shasum -a 256 "$W/macOSUpdCombo10.13.6.dmg"
hdiutil verify "$W/macOSUpdCombo10.13.6.dmg"
hdiutil attach -readonly -nobrowse -mountpoint "$W/mount" "$W/macOSUpdCombo10.13.6.dmg"
pkgutil --check-signature "$W/mount/macOSUpdCombo10.13.6.pkg"
(cd "$W/extract" && xar -xf "$W/mount/macOSUpdCombo10.13.6.pkg" 'macOSUpdCombo10.13.6.pkg/Payload')
hdiutil detach "$W/mount"
python3 bridge/tools/unpack_pbzx_checked.py "$W/extract/macOSUpdCombo10.13.6.pkg/Payload" "$W/extract/high-sierra-payload.cpio"
(cd "$W/extract/bundles" && bsdtar -xf ../high-sierra-payload.cpio \
 './System/Library/Extensions/GeForceVADriver.bundle' \
 './System/Library/Extensions/GeForce.kext' './System/Library/Extensions/IOAcceleratorFamily2.kext')
```

For the pinned comparison, `R` is the retained private lab results directory and `H` is `$W/extract/bundles/System/Library/Extensions`. The prior Sierra artifacts are acquired separately as in [the historical dependency documentation](DEPENDENCIES.md). A changed input is rejected, not silently repinned.

```sh
H="$W/extract/bundles/System/Library/Extensions"
python3 bridge/tools/audit_high_sierra_video.py \
 --sierra-provider "$R/video-sierra-provider-20261027-01/GeForceVADriver-10.12.6.private" \
 --high-provider "$H/GeForceVADriver.bundle/Contents/MacOS/GeForceVADriver" \
 --current-provider /System/Library/Extensions/GeForceVADriver.bundle/Contents/MacOS/GeForceVADriver \
 --sierra-ge "$R/video-sierra-kernel-contract-20261027-01/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce" \
 --high-ge "$H/GeForce.kext/Contents/MacOS/GeForce" \
 --current-ge /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
 --high-io "$H/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2" \
 --out /absolute/new-high-sierra-audit.json
python3 -m unittest discover -s tests -p 'test_audit_high_sierra_video.py' -v
python3 -m unittest discover -s tests -p 'test_compare_va_candidate.py' -v
python3 -m unittest discover -s tests -p 'test_unpack_pbzx_checked.py' -v
```
