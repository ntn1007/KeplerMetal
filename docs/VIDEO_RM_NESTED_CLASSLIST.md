# NVIDIA class-list nested-buffer path

The pinned on-disk NVDAResman contains a control-table entry for `0x800201`
and code that prepares and releases an embedded array buffer. This is the
specific pointer path left open by the [outer-control audit](VIDEO_RM_CONTROL_PATH.md).
It is still static evidence: no class-list request was issued and no video
engine was exercised.

## Table and handler

The on-disk table at `0x28a370` has 81 non-null entries followed by a null
terminator. Entry 62 at `0x28a750` contains command `0x800201`, metadata
`0x00030010`, and a file-backed pointer to `0x12e0d9`. The lower 16 bits of
that metadata agree with a 16-byte parameter block. The pointer has an
original nonexternal, eight-byte `__TEXT,__text` relocation at `0x28a758`;
the raw value is not a live kernel address.

Function `0x12ccd4` supplies that table to `0x4537f`. The latter asks
`0x451c3` to find a command, validate the 16-bit size and applicable flags,
prepare the outer parameter buffer, and then call the matching entry's function
pointer. This connects the entry to the handler conditionally in the on-disk
control-table path. The complete route from a particular real user client to
`0x12ccd4`, including object lookup and indirect class dispatch, is **not**
established here.

The `0x12e0d9` handler takes a parameter pointer from the control context,
reads its nested pointer at offset 8 and tail-calls `0x12ed71`. When that
nested pointer is non-null, `0x12ed71` constructs a buffer descriptor whose
32-bit byte length is the first parameter word shifted left by two. It calls
`0x3307c` to prepare access, invokes an indirect backend method with the
prepared buffer, and calls `0x332ab` to finish it. With a null nested pointer
the descriptor preparation is skipped and the backend receives a null buffer.
The actual backend method and its count semantics have not been qualified.

## Copy and bounds observations

For a nonempty descriptor, `0x3307c` either passes a pointer through or
allocates a temporary buffer, depending on its flags and the result of client
classification at `0x33259`. In the temporary-buffer case shown in this
function, it invokes a copy-in helper; `0x332ab` invokes a copy-out helper on
the success path, then frees the temporary buffer. The underlying helpers use
`IOMemoryDescriptor` for a non-kernel task and check completion and the byte
count; the kernel-task branch uses `memmove`. Error paths and flags can change
or suppress copying. These observations do not prove which branch an eventual
user request takes or that the nested pointer's lifetime is valid.

The multiplication in `0x12ed71` occurs in a 32-bit register. The allocator
helper contains a one-MiB size comparison on one branch, after this shift;
other flag/identity branches exist. Do **not** infer a universal class-count
limit or an exploitable bug from this observation. A future caller must apply
its own strict pre-multiplication bound, independently validate the returned
count against its allocated capacity, and stop on any ambiguous status. The
existing [offline classifier](../bridge/experiments/video_classlist/offline.py)
already caps separately supplied arrays at 65,536 words; that is a project
analysis limit, not a GPU or driver limit.

The valid RM root/device handles, actual user-route reachability, live address
space and buffer ownership, concurrent count changes, success/error semantics,
and cleanup are still open. The historical root allocation/free witness has
not been run on the changed system profile. This analysis does not authorize a
new RM request or modify installed components.

## Reproduction

The [receipt](video-rm-nested-classlist-validation.json) records SHA-256 pins
and ten complete receiver functions, table integrity, the handler's local
relocation, and selected direct call/jump edges. Ghidra's terminal-call and
indirect-dispatch limitations remain relevant. `0x4537f` calls the table
entry indirectly; the verifier checks the table contents and relocation, not a
live call. The two underlying copies were also separately inspected through
the REA evidence bundle. No vendor binaries or disassembly are published.

```sh
R="$KP_LAB/bridge/results"
python3 -B bridge/experiments/video_classlist/nested_audit.py \
  --image /System/Library/Extensions/NVDAResman.kext/Contents/MacOS/NVDAResman \
  --rea "$R/video-rm-nested-pointer-rea-20261028-01.private.json" \
  --out /absolute/new-nested-audit.json
python3 -B -m unittest discover -s tests -p 'test_video_nested_audit.py' -v
```

The retained private REA 6.4.0 / Ghidra 12.1.4 bundle is required by its exact
hash; recreating it with different metadata requires an independent review.
No GPU work or private RM call is performed by these commands.
