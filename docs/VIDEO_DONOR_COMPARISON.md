# Kepler video: donor and installed GeForce comparison

A read-only comparison now covers the complete pre-signature portion of the
installed GeForce kernel extension against one identified upstream donor. The
donor is the `12.0 Beta 6-23.4` GeForce kext in
[PatcherSupportPkg at revision 3250ca0](https://github.com/dortania/PatcherSupportPkg/tree/3250ca07ca49e3f8c743066381b5688028681de8/Universal-Binaries).
The [OCLP Kepler patchset at its research revision](https://github.com/dortania/OpenCore-Legacy-Patcher/blob/d622cd5de86e5cb9a8c975c2809dbdbd2822c86e/opencore_legacy_patcher/sys_patch/patchsets/hardware/graphics/nvidia_kepler.py)
selects that donor directory for the corresponding later OS versions. This
selection is provenance, not proof that an installation used that exact file.

The downloaded donor's Git blob ID is `35f2746a265dc78c3b40f43369b38affe1aa6c42`
and its SHA-256 is `dc666a02220d8d196a426e0e23d5a2d4c44719b70cee0ac9464d0b20845ed846`.
The installed file's SHA-256 is
`44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3`.
Both are thin x86_64 Mach-O files. Their signatures start at offset 1,026,192;
the donor signature is 31,504 bytes and the installed signature is 31,584 bytes.

Among all 1,026,192 bytes before that offset, only **two byte positions** differ:
one in `__LINKEDIT.filesize` and one in `LC_CODE_SIGNATURE.datasize`. Each field
was checked against its own actual file length and terminal signature range.
After normalizing only those two validated size fields, the two pre-signature
byte sequences match completely, SHA-256
`5c21e03f40e7609e3ab688be17363700d04516a7046e8744236673cf2e5520f3`.
A second independent raw-byte check found the same two differences. The
signature contents themselves differ and were not authenticated by this test.

The separately archived October 18 file has SHA-256
`c735877fe16b1495a7010c707ea355c4f312465bda4cdb0b8d99ab7f34247557` and
**was not recovered**. Its archived 28 table words and relocation records, and
11 selected method ranges totaling 1,217 bytes, match both the donor and the
current file. These samples do not establish complete identity with the missing
historical file. Matching on-disk bytes also do not establish loaded kernel bytes,
correct resource lifetime, video-engine execution or runtime compatibility.

The archived root-client launcher was invoked in its unprivileged `mock` mode
with its original frozen build. It refused the changed driver profile **before
creating the result directory or launching a native host**, as designed. An
initial attempt used an invalid output directory and was separately rejected by
the path guard; it is not counted as the driver-profile control. The original
profile has not been changed or accepted automatically.

A read-only attempt to attach the local OCLP support image did not complete;
the experiment's own attachment process and helper were terminated, and no
image was listed as attached afterward. The donor above was instead retrieved
from the pinned upstream repository and its Git blob hash verified. No driver,
framework, OCLP file, boot setting or system protection was modified.

## Reproduction

Obtain the donor locally from the pinned upstream revision using the donor path
specified above, with the applicable license. Never place vendor binaries in this
repository. Then run the source-only comparator:

```sh
python3 tools/compare_signing_layout.py "$KP_LOCAL_DONOR" \
  /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce
python3 -m unittest discover -s tests -p test_signing_layout.py -v
```

The comparator requires a thin x86_64 Mach-O, a valid bounded SuperBlob, a
single `__LINKEDIT` segment and a signature that terminates both that segment
and the file. It compares every byte before the signature after normalizing
only the two constrained size fields. A different layout is reported as
incomparable. This tool never changes an allowlist, authenticates a signature or
claims a usable decoder. See [validation fingerprints](video-donor-validation.json).
