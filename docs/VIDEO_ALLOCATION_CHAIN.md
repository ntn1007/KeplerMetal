# Static NVIDIA video-buffer allocation chain

A read-only analysis of the installed, hash-pinned IOAcceleratorFamily2 and GeForce files narrows the video-buffer allocation path. It does **not** execute the path, establish valid private requests, or demonstrate video decoding. The prior [guarded request](VIDEO_BUFFER_REQUEST_GUARD.md) stopped before selector 3 and the [reply analysis](VIDEO_REPLY_CONTRACT.md) did not qualify a real reply.

The checked file instructions, symbol targets and on-disk vtable relocations establish the following **conditional static chain** on this profile:

1. The NVIDIA video-context table names inherited `IOAccelContext2::getDataBuffer` and `allocOneDataBuffer`. The first checks an object-dependent class bound and contains a virtual allocation call. The class count, object state and live vtable are not observed here.
2. The inherited allocator passes context/shared fields and class-dependent values to `IOAccelResource2::newDataBufferResource`. Its factory requests resource type 10 through accelerator slot `0x8d0`. On disk the NVIDIA accelerator's corresponding slot relocates to the inherited `createResource`.
3. The inherited `createResource` calls accelerator slot `0xa70`; the NVIDIA table points that slot to `nvAccelerator::newResource`. That method allocates `0x400` bytes for an `nvTextureBuffer` object and invokes its constructor. **This is an object size, not a frame, decoded surface or VRAM allocation size.** Its constructor installs the `nvTextureBuffer` vtable.
4. The same on-disk resource vtable points initialization slots `0x138` and `0x140` to NVIDIA methods and memory slot `0x128` to inherited `IOAccelResource2::allocDataBufferMemory`. The allocator calls the initializer with two zero arguments before attempting the memory method; its failure branches invoke `databuffer_release`.
5. The inherited memory method contains a conditional virtual accelerator call and `lock_vidmem`, plus a system-memory allocation path and a conditional task-mapping call. The NVIDIA accelerator table's slot `0x8c0` names `createVidMemory`. The conditions, object identities, returned memory, actual path and cleanup of a live request remain unverified.

The finding identifies concrete objects and conditional backing paths to observe in a legitimate client. It does not justify fabricating a context, calling a private selector or forwarding the previously refused request. Static file relocations do not prove loaded vtable targets or execution. No Metal API extension, performance result or hardware-video success is claimed.

The vendor's [418.113 GPU table](https://download.nvidia.com/XFree86/Linux-x86_64/418.113/README/supportedchips.html) lists GTX 880M PCI `1198` as VDPAU feature set D; its [VDPAU documentation](https://download.nvidia.com/XFree86/Linux-x86_64/418.113/README/vdpausupport.html) describes supported decoder profiles for that set on Linux. This is hardware/driver reference evidence, not proof of the macOS decoding path. Archived macOS tests still return `-12906` and zero hardware images.

## Reproduction

The source-only auditor reads the exact two installed binaries and three private REA evidence bundles. It verifies 10 function-region hashes, 8 vtable slots, direct-call displacements, selected instructions, the mapping relocation, 8 REA evidence records and five input-tamper refusals. Output contains identifiers and hashes, not vendor instructions. The full REA bundles contain proprietary disassembly and remain in the local lab. The audit performs no native driver calls or GPU dispatch.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
python3 bridge/tools/video_allocation_chain.py \
  --io /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2 \
  --ge /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --kernel "$LAB/results/video-allocation-kernel-20261028-01.private.json" \
  --nvidia "$LAB/results/video-allocation-nvidia-20261028-01.private.json" \
  --backing "$LAB/results/video-allocation-backing-20261028-01.private.json" \
  --out "$LAB/results/video-allocation-chain-new.json"
python3 -m unittest discover -s tests -p test_video_allocation_chain.py -v
```

[Sanitized validation record](video-allocation-chain-validation.json). The evidence uses REA 6.4.0 / Ghidra 12.1.4. The two installed input hashes are in the record; a changed profile refuses rather than repinning. A subsequent live observation would need its own isolated, authorized client, identity and lifetime qualification. No system component, OCLP or firmware was modified.
