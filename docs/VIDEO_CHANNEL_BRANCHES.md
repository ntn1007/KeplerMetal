# NVIDIA video-channel access: three on-disk profiles

A read-only comparison revisits the older private-lab channel analysis and extends its direct-branch inventory to the [signed High Sierra components](VIDEO_HIGH_SIERRA_COMPARISON.md). The audit checks both `call` and `jmp` instructions, verifies their `rel32` target from file bytes, and records their nearest preceding defined Mach-O symbols. That symbol is an attribution aid, not proof of a function boundary or runtime execution.

| Pinned GeForce image | Direct branches decoded to `AcquireChannel` | Relevant observation |
| --- | --- | --- |
| Sierra 10.12.6 | Four calls and one tail jump | One call is at `0x5ec35`, inside the symbol range beginning at `nvVideoContext::acquire_channel` (`0x5eb02`); this is the historical handler associated with `0x105` in the [earlier table audit](VIDEO_PROVIDER_DISPATCH.md). |
| High Sierra 10.13.6 | One call and one tail jump | The call at `0x54bf2` is within the range following `nvSubmitter::AllocateChannel` (`0x54a90`). The video-named wrapper at `0x14de0` jumps to the manager at `0x14de5`. |
| Current on-disk GeForce | One call and one tail jump | The call at `0x55ba5` follows `nvSubmitter::AllocateChannel` (`0x55a64`). The video-named wrapper at `0x14c56` jumps at `0x14c5b` to `AcquireChannel` at `0x148a6`. |

The decoded direct branch inventory found **no direct call or jump to the video-named wrapper** in any of these three files. That is a bounded negative search, not proof of unreachability: indirect calls, virtual dispatch, other modules, code not decoded as instructions and runtime-generated paths are outside the inventory. REA/Ghidra 12.1.4 independently reports the current wrapper as a 10-byte function ending in the jump to `0x148a6`, with no incoming references in that analysis. Evidence `ev_fc12dc2370926290aabb797a604fcd70c18a4cc7d26b2b545264152ac351cdfe` is retained privately. The decompiler's inferred C signature is not an ABI certificate.

The previous Sierra/current channel audit remains a separate piece of evidence. Re-auditing it on this profile preserves its result: the current manager and object jump tables include conditional paths for internal types 3, 4 and 5 toward `CreateObjectVideo`; the current direct submitter call's inspected type assignments are 1 and 2. The new public audit independently verifies the pinned jump-table entries and selected instructions. For a zero class field, `CreateObjectVideo` has a return-zero branch before `CreateObject`; **zero alone does not prove object creation**. Runtime class values, guards, actual dispatch and ownership remain unobserved.

These findings identify a missing *demonstrated route* between the historical video context and the currently retained channel machinery. They do not establish that the wrapper is unusable, that Sierra's private `0x105` ABI is valid on Tahoe, that a channel was created, or that decoding works. No video selector, native driver routine or GPU command was executed here; no system component, OCLP or firmware was modified. No proprietary binaries or disassembly are published.

## Verification

[Machine-readable results](video-channel-branches-validation.json) retain image hashes, direct-branch addresses and instruction hashes. REA's source-bound evidence remains private. The audit runs `llvm-objdump` and independently validates each listed five-byte relative target. Negative tests reject omission of the tail jump, duplicate branches and altered opcode/target. It does not prove that all bytes were decoded correctly or cover indirect edges.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
H="/Volumes/HDD/KeplerMetal-archives/high-sierra-10.13.6/extract/bundles/System/Library/Extensions"
python3 bridge/tools/audit_video_channel_callers.py \
 --sierra "$R/video-sierra-kernel-contract-20261027-01/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce" \
 --high "$H/GeForce.kext/Contents/MacOS/GeForce" \
 --current /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
 --out "$R/video-channel-branches-new.json"
python3 -m unittest discover -s tests -p 'test_audit_video_channel_callers.py' -v
```

The High Sierra recovery procedure and provenance are in [VIDEO_HIGH_SIERRA_COMPARISON.md](VIDEO_HIGH_SIERRA_COMPARISON.md). A different file hash or profile is refused. Future work must establish the actual allowed channel-creation interface, object classes, reference ownership and cleanup before any bounded video submission can be considered.
