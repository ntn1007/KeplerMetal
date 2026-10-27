# Shared-client resource release: static dispatch contract

The resource-wrapper finalizer can issue `IOConnectCallMethod` with selector 1
on its shared connection. On the pinned cache image, the call supplies **one
scalar input** and no scalar output; the input is derived from a 32-bit field
at offset `0x100` of resource-associated client data. The finalizer executes
this call only on a conditional reference-count path. This is a static finding;
no selector was sent during this analysis.

The pinned IOAccelerator kernel method table has a selector-1 entry for
`IOAccelSharedUserClient2::delete_resource`, with legacy flags 0, `count0=1`
and `count1=0`. Apple's [published XNU legacy dispatcher](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/iokit/Kernel/IOUserClient.cpp)
uses the scalar-input/scalar-output shim for that method type. This is a source
comparison, not proof the installed kernel is byte-identical to that source.
The SDK 26.2 kernel-mode compile confirms the descriptor layout and the
`IOExternalMethodArguments` scalar pointer at `0x20`, followed by its count at
`0x28`.

The installed NVIDIA subclass adds behavior before the generic method:

1. Its `externalMethod` checks for selector 1, reads the first scalar's low
   32 bits, and calls the shared-resource lookup. If lookup succeeds, it calls
   `nvAccelerator::DoPendingReleaseIfNeeded` with the lookup output.
   The pending-release routine itself tests a flag in the looked-up object.
   On one branch it clears the flag, may call one virtual method, calls
   another and updates linked-list pointers. These are static paths, not
   evidence that any particular live resource followed them.
2. It then forwards to the inherited shared-user-client dispatcher. Its
   `getTargetAndMethodForIndex` delegates selector 1 to the parent table when
   the required accelerator field is present; the NVIDIA-specific descriptor
   range is separate.
3. The parent `delete_resource` looks up the supplied ID in the shared
   namespace. A failed lookup returns `0xe00002c2`. If lookup succeeds, it
   checks a resource byte at offset `0x14`: value `0x0a` skips the indirect
   call, while other values reach a virtual method at slot `0x160`. The
   successful lookup path returns zero. **Zero alone does not prove that every
   underlying resource has been freed.**

The assembly shows the lookup output being loaded as the second argument of
`DoPendingReleaseIfNeeded`. Ghidra's pseudocode displayed a literal zero for
that argument; the recorded instructions take precedence over that particular
decompiler rendering. The NVIDIA selector-1 branch reads the scalar pointer
before entering the inherited dispatcher, with no local scalar-count check
visible before that read. Earlier system checks may exist and have not been
traced. Do not probe malformed input or infer a vulnerability from this static
observation.

This links the user-mode finalizer to a plausible kernel dispatch path, but
**neither the path nor the cleanup has been observed at runtime**. The raw
association witness did not call the selector, and the actual resource ID,
resource type, mapping lifetime and failure cases are not yet qualified. The
next work is to observe a legitimate resource produced by an ordinary client
and establish its lifetime; do not invent an ID or submit a guessed command to
the display GPU.

## Reproduction

The offline checker requires the exact installed binaries, seven private local
REA captures, and optionally the exact SDK/cache and prior private finalizer
capture. It checks the actual legacy table, both subclasses' vtables, original
relocations, named function identities, selected instructions and the native
user-mode call shape. It emits identifiers and hashes; vendor code and
analysis captures are not redistributed. `--sdk-check` compiles assertions
only. Use a fresh output path.

```sh
python3 bridge/tools/video_shared_delete_contract.py \
  --ioaccel /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2 \
  --geforce /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --io-rea "$KP_LAB/bridge/results/video-shared-selector-ioaccel-20261027" \
  --ge-rea "$KP_LAB/bridge/results/video-shared-selector-geforce-20261027" \
  --pending-rea "$KP_LAB/bridge/results/video-shared-pending-release-20261027" \
  --sdk-check \
  --cache /System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64 \
  --finalizer bridge/results/video-buffer-finalizer-resource-20261027-01 \
  --out /absolute/new-shared-delete-audit.json
python3 -m unittest discover -s tests -p test_video_shared_delete_contract.py -v
```

[Recorded identities and hashes](video-shared-delete-validation.json). No
system driver, OCLP, firmware, protected configuration, resource or GPU state
was modified by this offline analysis.
