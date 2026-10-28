# NVIDIA video class-list provenance

The [prior comparison](VIDEO_NOUVEAU_CLASS_COMPARISON.md) identified three video class candidates in the macOS NVIDIA driver but could not observe the list from which the driver selects them. This analysis locates the **on-disk producer of that list** and compares it to a published NVIDIA interface. It does not retrieve the iMac's live class list or implement hardware video.

In the pinned GeForce image, `nvAccelerator::InitializeDevice` (`0x93dc`) contains a direct call to `InitClassList` (`0xc842`) before a direct call to `CreateAndInitHALEv`. In the inspected `InitClassList` body, two external call relocations resolve to `_NvRmControl`. Both pass command `0x800201` and a 16-byte parameter block. The block is zeroed before the first call; after that call, its first 32-bit word is stored as a count, multiplied by four for an allocation, and a resulting pointer is placed at block offset 8 before the second call. The driver's stored pointer and count are at offsets `0x1660` and `0x1668`, the fields read by the previously examined `GetFirstClassSupported`.

NVIDIA's public [515.43.04 control header](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/1739a20efc4acb55fd1dc53dcc66057b70c2613c/src/common/sdk/nvidia/inc/ctrl/ctrl0080/ctrl0080gpu.h) identifies the **same number** as `NV0080_CTRL_CMD_GPU_GET_CLASSLIST` and describes a count query followed by a list query. The identical declaration was checked in a newer pinned public header. A small x86-64 C11 build using the extracted declaration and modeled `NvU32` confirms size 16, count offset 0 and pointer offset 8 with the pinned NVIDIA 64-bit pointer and Clang alignment definitions. This is a strong static correspondence, not proof that every detail of the newer open-driver ABI applies to the older macOS driver or GTX 880M.

The [audit](video-classlist-provenance.json) pins the full image, two complete function bodies, selected instructions, the direct call targets, both original Mach-O relocations, the NVIDIA headers and REA evidence. The `InitClassList` analysis is evidence `ev_a1eeaa10ab9299e94ad109b2760ee9c3390925aaf775cdb4cfc639123d8e6ebc`; the caller analysis is `ev_d8f7af523728ae987aee4a1891b6d71cd7f60779ab314cd82396957fe334d5e1`. REA/Ghidra 12.1.4 analyzed a temporary copy; the proprietary evidence bundle remains private. All observations of driver code are static and file-backed, not a trace of the currently loaded kernel or class-list contents.

## Offline classifier

[`offline.py`](../bridge/experiments/video_classlist/offline.py) classifies a **separately obtained** little-endian array against the static candidate priority. It requires an explicit count and exact byte length, bounds inputs and never dereferences the NVIDIA pointer or contacts a driver. Its output always says that the input's authenticity and hardware provenance are unverified. Synthetic CPU tests cover preferred and fallback classes, empty lists, malformed lengths, invalid counts and changed audit instructions; these are not actual GPU observations.

The public NVIDIA sources target a newer driver generation and do not establish Kepler support in the open kernel modules. There is no known qualified unprivileged way here to obtain the kernel-owned list. A successful prior administrator port open did not establish this RM control's user-mode transport or authorize inventing a packet. Do not submit this command to the display GPU on the strength of this comparison. Future work must identify a legitimate existing observation or qualify the exact transport, ownership and authorization before asking the device for anything.

## Reproduction

The exact references were downloaded locally, not redistributed. The 515 tag resolves to commit `1739a20efc4acb55fd1dc53dcc66057b70c2613c`; the later reference is `ca2d03e6fafd4d4b56b383497d931c25b283bfcf`. The three MIT-licensed reference files are the [515 control header](https://raw.githubusercontent.com/NVIDIA/open-gpu-kernel-modules/1739a20efc4acb55fd1dc53dcc66057b70c2613c/src/common/sdk/nvidia/inc/ctrl/ctrl0080/ctrl0080gpu.h), the [515 types header](https://raw.githubusercontent.com/NVIDIA/open-gpu-kernel-modules/1739a20efc4acb55fd1dc53dcc66057b70c2613c/src/common/sdk/nvidia/inc/nvtypes.h), and the [later control header](https://raw.githubusercontent.com/NVIDIA/open-gpu-kernel-modules/ca2d03e6fafd4d4b56b383497d931c25b283bfcf/src/common/sdk/nvidia/inc/ctrl/ctrl0080/ctrl0080gpu.h). Save them as `ctrl0080gpu-515.h`, `nvtypes-515.h` and `ctrl0080gpu.h` respectively. Their hashes are recorded in the audit. The private REA bundle must also be retained or recreated and independently qualified. The auditor refuses different inputs. It compiles and runs a temporary CPU-only layout assertion, reads the driver file, and emits no GPU or private RM calls.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
python3 bridge/experiments/video_classlist/audit.py \
  --driver /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --rea "$R/video-classlist-rea-20261028-01.private.json" \
  --references "$R/video-classlist-reference-20261028-01" \
  --out "$R/video-classlist-static-audit-new.json"
python3 -m unittest discover -s tests -p 'test_video_classlist.py' -v
```

No macOS framework, driver, OCLP, firmware or protected setting was modified. No hardware decoding, new Metal feature or performance improvement is claimed.
