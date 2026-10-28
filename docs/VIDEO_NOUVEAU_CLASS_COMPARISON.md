# Kepler video classes: Nouveau and the macOS NVIDIA driver

The pinned Mesa 26.2.4 source and the current on-disk GeForce kernel image contain the **same three candidate video object class numbers**. This is evidence for a more specific investigation of the missing macOS video transport, not a working decoder or proof that a Linux command buffer can be sent to macOS.

| Nouveau Kepler path | Nouveau class | macOS `InitClasses` candidates | Conditional channel-object field and type |
| --- | --- | --- | --- |
| BSP / MSVLD | `0x95b1` | `0x95b1`, then `0x90b1` | `+0xff4`, type 11 |
| VP / MSPDEC | `0x95b2` | `0x95b2`, then `0x90b2` | `+0xff8`, type 8 |
| PPP / MSPPP | `0x90b3` | `0x90b3` | `+0xffc`, type 10 |

In Mesa's `nvc0_create_decoder`, the `chipset >= 0xe0` branch creates three engine-specific channels and binds those three classes. The decoder's end-frame path invokes BSP, VP and PPP in that order. Mesa's class header names the first two GK104 classes; the third is named GF100 MSPPP. Its public UAPI engine masks are BSP `0x08`, VP `0x02` and PPP `0x04`. These are Nouveau/Linux interfaces, not macOS IOConnect selectors.

The inspected NVIDIA `nvFermiHAL::InitClasses` at `0x2cb9a` passes each ordered candidate list to `nvHAL::GetFirstClassSupported` at `0x3e64c` and stores its return in the three fields above. The latter scans a separately supplied class list and returns zero when no candidate matches. `nvHAL::CreateObjectVideo` at `0x3e90a` conditionally selects the same fields for the indicated channel-object type. These are file-backed instructions and a static control-flow interpretation; no execution of these functions, supplied class list, live class value or valid channel has been observed. In particular, the type numbers here are the field at the channel object, not automatically the manager's types 3/4/5 in [the previous analysis](VIDEO_CHANNEL_BRANCHES.md).

The current public registry read reports `IOVARendererID = 0x01040008` and `IOVARendererSubID = 3` on the one observed `nvAccelerator` service. The pinned on-disk `nvAccelerator::SetAccelProperties` produces that pair for **either** `0x95b1` or `0x90b1`. This observation is consistent with the static branches, but does not establish that those exact on-disk bytes set the live properties or determine which class is active. Registry properties are not proof of a usable hardware video engine.

## Firmware and compatibility boundaries

For the inspected Mesa source, the explicit userspace firmware-file load is limited to chipsets below `0xd0`; its later-architecture availability check still tries to create a BSP object. Therefore the absence of a userspace firmware-file read on the Kepler branch must **not** be interpreted as proof that firmware is unnecessary or initialized under macOS. Kernel initialization and firmware state were not inspected at runtime.

NVIDIA's [418.113 VDPAU documentation](https://download.nvidia.com/XFree86/Linux-x86_64/418.113/README/vdpausupport.html) documents decoder profiles and limits for its Linux feature sets. The [NVIDIA 418.43 GPU table](https://download.nvidia.com/XFree86/FreeBSD-x86_64/418.43/README/supportedchips.html) identifies PCI device `1198`, GTX 880M, as feature set D. These references describe NVIDIA's Unix driver, not the functionality exposed by the current macOS stack.

An actual decoder still requires a qualified channel-acquisition route, successful runtime class and object selection, address-space mappings and resource lifetimes, submission and synchronization protocols, and independently checked frames. The earlier hardware-required VideoToolbox tests remain failures with zero images. No vendor provider, private selector or GPU workload was launched for this comparison; no system, driver, OCLP or firmware modification was made.

## Evidence and reproduction

The [machine-readable record](video-nouveau-class-comparison.json) pins the Mesa archive, four source files, the installed GeForce image, four complete function ranges and their REA/Ghidra evidence IDs. The auditor compares the source files against their exact members in the locally retained archive, independently checks selected instruction bytes, the eight-entry jump table and property names, and reads the current registry. It does not publish vendor binaries or disassembly. The Mesa tree was extracted without a nested Git checkout; commit `96cb43121031992b85767f9c1be8f3f48e22b1d2` is the previously recorded upstream reference, while the archive and members are directly hash verified here. The private REA bundle is SHA-256 `401a07db63b466ad08f5dae49d9d4684fa50905167325508cae61dd1bc83c3dc`.

Use the exact local sources and private REA bundle, a fresh output path, and the current recorded service/profile. A changed image or boot-specific registry ID is refused; qualify it separately.

```sh
V="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/vendor"
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
python3 bridge/tools/audit_video_nouveau_classes.py \
  --archive "$V/mesa-26.2.4.tar.xz" --tree "$V/mesa-26.2.4" \
  --driver /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --rea "$R/video-nouveau-class-rea-20261028-01.private.json" \
  --out "$R/video-nouveau-class-comparison-new.json"
python3 -m unittest discover -s tests -p 'test_video_nouveau_classes.py' -v
```

The next investigation should establish, by a bounded observation of legitimate initialization or saved class-list provenance, which candidates are actually selected and how an existing macOS client obtains a video channel. Matching constants alone is insufficient to submit video work safely.
