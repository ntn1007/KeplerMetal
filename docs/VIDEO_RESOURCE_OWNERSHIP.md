# Video context association and resource lifetime: static evidence

The existing type-3 video-context open/close test succeeded on the qualified
profile. This document investigates the next dependency without opening any
new connection. It does **not** demonstrate video decoding, allocation,
association or cleanup after association on the running system.

The pinned NVIDIA `nvVideoContext` vtable has file relocations to the inherited
`IOAccelContext2::connectClient` (slot `0x918`), `start` (`0x5c0`) and
`clientClose` (`0x8f0`). Its `contextStop` slot instead points to the NVIDIA
subclass's own method at `0x68340`. These are on-disk observations, not live
relocated addresses. The general [IOConnectAddClient documentation](https://developer.apple.com/documentation/iokit/1514609-ioconnectaddclient)
specifies two connections but does not establish this private driver's complete
contract or a safe calling sequence.

In Ghidra's analysis of the pinned IOAccelerator file,
`IOAccelContext2::connectClient` at `0x83b4` checks the supplied client for the
`IOAccelSharedUserClient2` class, compares accelerator and task identities, and
rejects an already attached context. On the analyzed successful path, it stores
a shared object at context offset `0x5a0`, increments its context reference
count, retains objects, and calls virtual slot `0x5c0`. The NVIDIA vtable file
relocation for that slot names the inherited `IOAccelContext2::start`.
The comparison of fields and the call are verified against recorded
instructions; their object interpretation comes from the Ghidra analysis and
associated symbols. A previous static factory analysis associates type 6 with
creation of a shared client. A subsequent [same-process Metal test](VIDEO_SHARED_METAL.md)
observed successful type-6 open/close; a successful association has not been
observed.

The inherited `IOAccelContext2::contextStop` at `0x7eea` calls
`freeAllDataBuffers`, decrements the shared context reference and clears the
shared pointer when present. The `freeAllDataBuffers` body traverses resource
lists and calls `IOAccelResource2::databuffer_release` before releasing
objects. The inherited `clientClose` branches through virtual slots `0x600` or
`0x678`, which resolve in the NVIDIA file to `terminate` and `detach`.

The static teardown chain is now narrower: the NVIDIA file points its `stop`
slot to `IOAccelContext2::stop` at `0x7880`. That method calls virtual
`contextStop` through slot `0x9e8`, which points to NVIDIA's override at
`0x68340`. The override jumps through a relocation naming the parent
`IOAccelVideoContext2` vtable; its corresponding slot points to
`IOAccelVideoContext2::contextStop` at `0x3a062`. That method updates video
bookkeeping and jumps through the `IOAccelContext2` vtable to the inherited
`contextStop` at `0x7eea`. These are pinned instructions and on-disk table
links, not a runtime trace.

We have **not** established that a live close reaches this chain after
association, nor the cleanup order on failure. The shared client's
`clientClose` has its own state-dependent termination path. A previous
unassociated open/close does not resolve these questions.

This matters because `getDataBuffer` can allocate or reuse and map resources.
Even a correctly sized selector input does not define an ownership protocol.
Before a live association or resource request, qualify the subclass start/stop
paths, shared-client creation and both close orders, failure handling, and the
exact context and process requirements. Keep any prospective tests isolated,
profile-gated and serialized on the shared GPU reservation. No arbitrary
selector, malformed packet, firmware, system component or driver modification
is authorized by this analysis.

## Reproduction

The captures are local lab evidence: they contain decompiled vendor code and
are intentionally not redistributed. The checker requires the exact original
files, their SHA-256 hashes, ten REA response captures and instruction
anchors. It emits only identifiers, hashes and static slot metadata.

```sh
python3 bridge/tools/video_resource_ownership.py \
  --ioaccel /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2 \
  --geforce /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --link "$KP_LAB/bridge/results/video-ownership-link-20261027" \
  --ownership "$KP_LAB/bridge/results/video-ownership-20261027" \
  --nvidia "$KP_LAB/bridge/results/video-nvidia-stop-20261027" \
  --parent "$KP_LAB/bridge/results/video-parent-stop-20261027" \
  --out /absolute/new-ownership-audit
python3 -m unittest discover -s tests -p test_video_resource_ownership.py -v
```

[Recorded result and evidence identifiers](video-resource-ownership-validation.json).
The analysis used REA 6.4.0 with Ghidra 12.1.4. Capture integrity and selected
instructions are checked; decompilation, indirect calls and code paths still
require human interpretation. No change to macOS, OCLP or installed drivers.
