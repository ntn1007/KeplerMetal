# Video research: historical profile drift

The video-driver experiments archived on October 18 used an exact system
profile. A read-only recheck on October 27 compared that frozen 83-file
inventory with the installed paths: 78 hashes still match and **five differ**.
The old privileged RM witness remains unqualified on the changed profile; no
RM allocation or GPU command was submitted during this recheck.

The changed paths are the `GeForce` kernel extension binary, the
`GeForceMTLDriver` binary, the Metal framework binary, and the application
binary and Info.plist of OpenCore Legacy Patcher. This comparison does not
establish when or why any file changed. The Metal driver was separately
[compared and qualified for a bounded compute/render profile](DRIVER_PROFILES.md);
that earlier result does not qualify the unrelated video path or imply that
any other changed file differs only in a signature.

| Installed GeForce file | SHA-256 |
| --- | --- |
| Archived October 18 file | `c735877fe16b1495a7010c707ea355c4f312465bda4cdb0b8d99ab7f34247557` |
| Current file checked here | `44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3` |

The original video-context audit retained exact hashes for 11 selected function
ranges in GeForce: **1,217 bytes in total match** the current on-disk file at
the same offsets. All 28 original vtable words and their external relocation
metadata also match. The compared vtable words are the original on-disk values;
a Ghidra-relocated table is not directly comparable to unrelocated file bytes.

As an additional static check, Ghidra 12.1.4 produced matching disassembly,
pseudocode and outgoing references for `nvVideoContext::beginCommandStream`
at `0x68352` using the same analysis profile. The archived evidence ID is
`ev_82d51d4688e63ffca3f0b1dab4a9dcd7c0ed107887fda0486b219e82d70d81f7`;
the current evidence ID is
`ev_3da28650851aa5c17ce5f78541b808d6f250e6404415b769e7f3417ffd0e1fa9`.
The loaded and on-disk GeForce UUIDs also match the archived build UUID. A UUID
is not a hash of loaded kernel text.

These are partial comparisons, not a proof that either entire driver or its
video execution behaves identically. They do not identify the cause of the
changed file hash. The earlier historical audits still accurately describe
their dated experiments; re-running their strict system-inventory gates now
fails, as intended, because the profile changed. In particular, the prepared
RM root-client allocation/free test has not been executed on the current
profile. No NVIDIA/Apple binary or disassembly is distributed here.

## Reproduce the comparison

The following requires the retained local laboratory evidence, not included in
the public repository. Inputs are hash-pinned, output must be new, and the tool
does not change the acceptance profiles or open a GPU connection:

```sh
python3 bridge/tools/compare_video_profile.py \
  --inventory "$KP_LAB/bridge/results/video-local-xpc-progress-20261018/start.json" \
  --audit "$KP_LAB/bridge/results/video-command-contract-progress-20261018/command-contract-audit-01.private.json" \
  --geforce /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --prior-rea "$KP_LAB/bridge/results/video-command-contract-progress-20261018/GeForce-video-methods.private.json" \
  --current-rea "$KP_CURRENT_REA_RESULT" \
  --out /absolute/new-drift-result.json
python3 -m unittest discover -s tests -p test_video_profile_comparison.py -v
```

Both REA arguments may be omitted together to run the independent file-range
and relocation comparison alone. Recreating the current REA result requires
an independently configured Ghidra provider and the current on-disk file.
The result must be interpreted against its own file and analysis-profile hashes.
[Validation summary and fingerprints](video-profile-drift-validation.json). No video image,
performance improvement or broad driver compatibility is claimed by this diagnostic.
