# Static video-context method contract

A bounded analysis of the current on-disk `nvVideoContext` and the pinned
`IOAcceleratorFamily2` identifies the legacy method table associated with the
video-context path. This narrows the search for the video submission ABI; **no
selector, resource allocation, GPU command or decoder was executed here**.
The previously tested [type-3 open/close](VIDEO_CONTEXT_CURRENT.md) does not by
itself prove that any of these methods can safely be called.

The `nvVideoContext` vtable contains original external relocations for
`IOAccelContext2::externalMethod` and `getTargetAndMethodForIndex`, at offsets
`0x850` and `0x940` relative to the vptr in the inspected files. A third
relocation at slot `0xa68` names `IOAccelContext2::getDataBuffer`, with an
export at `0x9f70` in the pinned IOAccelerator file. The pinned
IOAccelerator analysis identifies the method table at `0x6e3a0`, with eight
48-byte entries. Addresses and relocation links are static file evidence; no
live relocated pointer or selector dispatch was observed.

| Index | Symbol in the pinned table | Flags | `count0` | `count1` |
| --- | --- | ---: | ---: | ---: |
| 0 | `finish` | 0 | 0 | 0 |
| 1 | `set_client_info` | 4 | 0 | variable |
| 2 | `submit_data_buffers` | 3 | 136 | variable |
| 3 | `get_data_buffer` | 3 | 8 | variable |
| 4 | `reclaim_resources` | 0 | 0 | 0 |
| 5 | `finish_fence_event` | 0 | 1 | 0 |
| 6 | null member pointer | 0 | 0 | 0 |
| 7 | `set_background_rendering` | 0 | 1 | 0 |

The variable marker is `0x00000000ffffffff` in the 64-bit count field. For
flags 3, Apple's [published XNU legacy method shim](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/iokit/Kernel/IOUserClient.cpp)
uses the two counts for input and output structure sizes. That source is a
comparison, not proof that the installed kernel's complete dispatcher is
byte-identical. The table also has a separate submit descriptor with flags
`0x13`, adding the SDK's foreground-only bit; the exact runtime branch and
policy effects have not been observed.

The actual SDK kernel header is compiled with `-DKERNEL` and confirms a 48-byte
`IOExternalMethod`, 16-byte C++ member pointer, and 64-bit `IOByteCount` at the
recorded offsets. A compile without `-DKERNEL` is intentionally rejected: on
this x86_64 SDK that mode produces a 40-byte descriptor and 32-bit counts.
The initial unspecialized compile failed for precisely this reason and is
retained in the local evidence; it must not be used to encode a kernel table.

A new Ghidra 12.1.4 analysis of the table's `get_data_buffer` body at `0x7144`
observes an input-length check for at least 8 bytes and an output-capacity check
for at least **48 bytes**, followed by a conditional virtual call through slot
`0xa68`. These are static code observations; the destination and the actual
resource returned have not been observed at runtime. The table's input-size
field is 8, while the function body itself tests a minimum of 8. Larger output
capacities also change a pointer passed to the virtual method, so variable
output does not mean that any capacity or buffer contents are valid.

A second new Ghidra analysis covers the static target at `0x9f70` (2,532
bytes). Its first input word is read as a 32-bit value and checked against a
context-dependent bound at offset `0x6dc`; the second 32-bit word participates
in a size-update calculation on one conditional path. The body contains a
virtual allocation call through slot `0xa70`; the corresponding file
relocation names `allocOneDataBuffer`. Resource reuse and release paths also
appear in the decompiler output. These observations identify a likely class
and size interface, but neither the valid class range nor its resource lifetime
has been established at runtime. A separate archived static path shows the
inherited `getDataBufferLimits` setting a count of two and `contextStart`
copying that count to the same context offset, conditionally on initialization.
Together these make indices **0 and 1 static candidates**, not verified valid
inputs for a live call. No allocator was called by the analysis.

The input lengths alone do not identify buffer handles, layouts, complete output
contents, command tokens, ownership, synchronization, access checks or cleanup.
The zero member pointer at index 6 is reported as a table fact; its runtime
behavior has not been tested. Sending an 8- or 136-byte buffer merely because
its size matches would not qualify the call. The Ghidra body for
`submit_data_buffers` contains state-dependent output sizing and resource
validation; its decompilation is evidence for further investigation, not a safe
encoder specification. The open-source XNU shim and this table do not establish
a complete ABI for the installed NVIDIA video stack.

## Reproduce

The analyzer requires the retained local REA bundle from the earlier lab work,
the exact pinned installed binaries and the qualified SDK. It reads the files
and compiles assertions; it does not open an IOKit connection. Output must be a
new directory. Vendor binaries and decompiled program bodies are not included
in this repository.

```sh
python3 bridge/tools/video_method_contract.py \
  --ioaccel /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2 \
  --geforce /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --prior-rea "$KP_LAB/bridge/results/video-command-contract-progress-20261018/IOAccel-command-contract-final.private.json" \
  --get-data-rea "$KP_LAB/bridge/results/video-method-contract-20261027/get-data-buffer.private.json" \
  --get-buffer-rea "$KP_LAB/bridge/results/video-method-contract-20261027/getDataBuffer.private.json" \
  --out /absolute/new-method-audit
python3 -m unittest discover -s tests -p test_video_method_contract.py -v
```

The two optional REA arguments may be omitted when those separately captured
evidence files are unavailable; the method table and SDK checks still run.

[Fingerprints and scope](video-method-contract-validation.json). No kernel,
OCLP, framework, hardware state or system driver was changed.
