# Third-party notices

Original KeplerMetal code is MIT-licensed. The export excludes complete external source trees and all proprietary components. Upstream context in patches retains the upstream terms; our root license does not replace them.

| Project | Reference used in the lab | Role | License / notice |
| --- | --- | --- | --- |
| [OpenNVDA](https://github.com/bdwithganesh/OpenNVDA) | `da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5` | AIR/NIR frontend, patch target | [Upstream MIT notice](third_party/licenses/OpenNVDA-MIT.txt), copyright 2026 bdwithganesh |
| [Mesa](https://gitlab.freedesktop.org/mesa/mesa) | 26.2.4, `96cb43121031992b85767f9c1be8f3f48e22b1d2` | NIR and NAK SM30 compiler | [MIT text](third_party/licenses/Mesa-MIT.txt); consult each upstream SPDX header. Patched NAK files include copyright 2025 Collabora, Ltd.; meson.build includes copyright 2017–2020 Intel Corporation. |
| [envytools](https://github.com/envytools/envytools) | `f102b82381f3f11cee113d16374c87091db039d9` | NVIDIA instruction and command documentation, assembler/disassembler | [Upstream MIT notice](third_party/licenses/envytools-MIT.txt) |
| [NVIDIA open-gpu-doc](https://github.com/NVIDIA/open-gpu-doc) | `9fdf5c4062007929d9f4e6cbad9c9771fe61b880` | QMDv00_06 field names/bit ranges, consulted reference | NVIDIA 2016 permissive header; referenced, not bundled. |
| [OpenCore Legacy Patcher](https://github.com/dortania/OpenCore-Legacy-Patcher) | source reference `d622cd5de86e5cb9a8c975c2809dbdbd2822c86e` | Installed stack provenance research | Referenced, not bundled; upstream license applies. |
| [WhateverGreen](https://github.com/acidanthera/WhateverGreen) | `093e76fec5655001f38b367dd22459c756ee89fa` | Read-only comparison of existing video renderer properties | BSD-3-Clause; referenced, not bundled or installed. |
| [FFmpeg](https://ffmpeg.org/) | Existing 9.0.2 FFmpeg/ffprobe executables on arm64; 7.1.5 source consulted for the VT format contract | Software H.264 reference; MPEG-2 software encode/decode and packet inspection | Separate external installation/references; no FFmpeg code or executable is bundled or linked into KeplerMetal. Its own build/license terms apply. |
| [Apple dyld](https://github.com/apple-oss-distributions/dyld) | `fd8d0c4d52320ebf64db34f3cb280310d905c5ae` | Public callback/cache format documentation consulted for the original inspector | Referenced, not bundled; upstream APSL notices apply to the external headers. |

`bridge/src/*.patch` are patches against the named open source revisions, not patches containing proprietary driver bodies. `bridge/src/opennvda-command-ir.inc` is an original extension to the OpenNVDA frontend. GPU programs are generated locally from included sources; no compiled program or captured vendor command stream is distributed.

The FP64 include contains an allowlist of program hashes, dimensions, and register counts, not program bytes. Other profile JSON files likewise describe test contracts and expected hashes; they do not grant rights to any external dependency.

Apple Metal, Xcode, macOS frameworks, restored Apple/NVIDIA drivers, NVIDIA Linux/FreeBSD packages, and firmware remain proprietary dependencies under their publishers' terms. They are not covered by this repository's MIT license and are not redistributed here. See [recovery instructions](docs/DEPENDENCIES.md).
