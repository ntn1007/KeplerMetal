# Exact driver profiles and boot-independent GPU identity

The 23 October investigation resolves the earlier profile refusal without
removing the driver fingerprint gate. The two admitted **whole-file** SHA-256
values are:

| Profile | `GeForceMTLDriver` SHA-256 |
| --- | --- |
| Original qualification | `2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054` |
| Current OCLP-restored file | `e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645` |

The original licensed local copy was compared with the installed file. Both
are 2,170,032-byte thin x86_64 Mach-O files. Exactly 262 bytes differ, all inside
the CMS signature payload. The load commands, code, data, CodeDirectory,
requirements and signature-container layout match byte for byte. The entire
file outside the code-signature range has SHA-256
`dfb45cc512a9425da0f7470211507e9396791794b6118f9db69b59ca81a2e76c`;
the matching CodeDirectory has SHA-256
`59ebd1ca00257e1622a312b199c0ef243de75b5445de098f9a6a91deb7e39d9c`.

This is an observation about these exact files. It does not prove certificate
authenticity or general runtime compatibility. Other Metal/framework/OCLP files
also changed relative to 19 October; the new system requires its own execution
qualification. No vendor binary or code bytes are distributed here.

## Read-only comparison

Given two independently obtained, licensed local copies:

```sh
python3 -B tools/compare_driver_signatures.py \
  "$KP_REFERENCE_DRIVER" "$KP_CANDIDATE_DRIVER"
```

The bounded parser validates Mach-O load-command sizes, the unique signature
range, SuperBlob indices, child ranges and non-overlap. It compares all bytes
except the CMS payload only when both layouts match. It reports hashes and
counts, never program bytes. Its deliberately limited input is thin x86_64
Mach-O with CodeDirectory and CMS wrapper; unsupported/malformed inputs fail.
Synthetic tests cover CMS-only changes, code/CodeDirectory changes and invalid
container bounds.

The format reference is Apple's
[`cs_blobs.h`](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/osfmk/kern/cs_blobs.h).
The comparison tool is diagnostic only: **it never authorizes another driver**.
The runtime and launcher still reject any file outside the two exact hashes,
even if a future file happened to have identical executable code.

## GPU identity across boots

The old trial hosts used registry ID `4294968458`. The current Metal device has
ID `4294968456`. Replacing one fixed ID with another would repeat the problem.

`bridge/src/KeplerGPUIdentity.h` uses public read-only IOKit queries to resolve
the actual registry entry identified by `MTLDevice.registryID`, then walks its
PCI ancestry. Selection requires the exact GTX 880M device name and NVIDIA PCI
vendor/device `10de:1198`. The HDMI-audio function `10de:0e0a` is not accepted.
The observed PCI ancestor currently has ID `4294967841`; that ID is recorded,
not hardcoded. The client rejects an ambiguous multiple-match selection.
This removes the fixed-ID dependency; no reboot or long-duration stress test
was performed during this qualification.

The helper resolves the system IOKit framework in-process, allowing existing
static-library clients to retain their linker flags. It changes no registry
property. The allocation API also uses this identity in place of its old
boot-specific ID. Its original native-program certificates remain bound to
their original code/library/metadata; the actual driver hash is reported
separately. Constructor type, image path, payload/metadata checks and ownership
remain enforced. Compute and graphics import evidence report the actual file
hash rather than the original profile's constant.

Fresh compute/CAS qualification and accounting observations are documented in
[MEMORY_ACCOUNTING.md](MEMORY_ACCOUNTING.md). This profile maintenance is not a
new NVIDIA hardware feature, a replacement installed driver, a performance
improvement, or a claim that every graphics/video path was requalified.

Other adapters still have historical gates: `KeplerCPUICB.mm`,
`KeplerNativeRenderDraws.mm` and `KeplerFP64.mm` retain old boot-ID checks, and
some also require the original file hash. They have not been silently admitted
by this change. Extending the same identity/profile contract to those adapters
requires their own command, rendering and numerical regression suites. Hardware
video, power/display integration and transparent ordinary-application support
also remain separate unfinished work.
