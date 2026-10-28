# Conditional current-kernel video selector path

This static audit connects the previously observed on-disk `nvVideoContext` relocations to instructions from the **actual matching kernel file**, rather than relying only on a comparison with published XNU source. It narrows the possible fate of historical selector `0x105`; it does **not** observe that selector, a live context or the kernel's loaded memory.

Under all of the following assumptions, the inspected synchronous path returns `kIOReturnUnsupported` (`0xe00002c7`) for selector `0x105`:

1. The actual object and runtime vtable targets correspond to the inspected GeForce and IOAccelerator file relocations.
2. `callExternalMethod` takes its normal branch, where the client flag bit `0x2` is clear. This branch passes a null dispatch pointer.
3. The tested `IOAccelContext2` context bit is set; selector `0x105` is not its special selector 6.
4. In `IOUserClient::externalMethod`, the input and output memory descriptor pointers and the **64-bit word at arguments +0x08** are zero. The retained matching KDK DWARF labels the field at +0x08 `asyncWakePort`, and the two descriptor fields at +0x40 and +0x68.

For this conditional path the base method calls the object's lookup at vtable offset `0x940`. The pinned IOAccelerator lookup returns null for a selector above 7, and the pinned kernel method returns `Unsupported` when the lookup result is null. When the context bit is clear, the IOAccelerator routine returns `kIOReturnNotReady` (`0xe00002d8`) on the inspected branch. These are deductions from instructions under stated assumptions, not observed IOKit results. The special dispatch for selector 6, nonzero dispatch pointer, asynchronous branch, descriptors and other client-flag branch are not qualified here.

## Evidence and limitations

The [audit](video-selector-path-validation.json) rechecks the installed GeForce and IOAccelerator SHA-256 and the on-disk kernel SHA-256 `7004ebc1020a5c7e3f075c631507f31fdc0ce3fe02e9f01f42dce1d178770a08`. `kern.uuid` matches the previously recorded kernel UUID. UUID equality does not establish equality of live kernel bytes, and none were read. The relocated vtable cells, exact function-range hashes and selected disassembled control-flow instructions are checked independently.

The two kernel functions are inspected through previously captured **non-loadable ELF ET_REL containers**. The audit verifies their section bytes and original virtual addresses against the exact on-disk kernel before decoding. The matching KDK DWARF field record is also hash-pinned. REA/Ghidra 12.1.4 independently analyzed the base method in the private container (evidence `ev_a79ccbd456f34561a5e5f4e204ceac60bef6ceca799b3d0f011fa36b805a7d1b`); its provider rebased the container by `0x100000`, so its `0xffffff8000b18640` entry corresponds to the on-disk link address `0xffffff8000a18640`. Decompiler types and outside targets remain uncertain; vendor code and evidence remain private.

The supplied `predict` function classifies only explicitly supplied assumptions; its outputs are **not observations** or a mechanism for issuing selectors. Tests reject invalid inputs, malformed ELF, changed relocations and altered instruction controls. The actual target connection, context flags, pointer values, live dispatch, other branches and hardware video remain unverified. No GPU command, private selector, driver installation or system modification was performed.

## Reproduction

Requires the original private lab captures, pinned machine profile and installed Xcode tools. A changed kernel UUID or input file is refused. This re-audit performs no GPU or IOKit operation:

```sh
LAB="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results/video-rm-emitter-carrier-progress-20261018"
python3 bridge/tools/video_selector_path_audit.py \
 --kernel /System/Library/Kernels/kernel \
 --ge /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
 --io /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2 \
 --lab "$LAB" --out "$LAB/../video-selector-path-audit-new.json"
python3 -m unittest discover -s tests -p 'test_video_selector_path_audit.py' -v
```

The earlier [method-table](VIDEO_METHOD_CONTRACT.md), [Sierra dispatch](VIDEO_PROVIDER_DISPATCH.md) and [channel-branch](VIDEO_CHANNEL_BRANCHES.md) analyses describe additional prerequisites. Establishing a safe real channel and decoding pipeline still requires explicit runtime evidence, resource ownership and cleanup, valid command transport, and independently checked output.
