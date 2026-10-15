# Obtain dependencies without redistributing drivers

No dependency download is required for the source-only runtime build. The following references support later experiments and historical comparisons. Downloads and extraction remain under ignored directories; they are not installed.

## NVIDIA Linux reference packages

NVIDIA publishes packages at its [official Unix archive](https://www.nvidia.com/en-us/drivers/unix/) and [download server](https://download.nvidia.com/XFree86/Linux-x86_64/). The lab compared 355.11, 418.113, 450.57, 470.63.01 and 470.256.02. URLs, sizes and recorded SHA-256 values are in [references.json](../dependencies/references.json).

```sh
python3 tools/fetch_references.py --list
python3 tools/fetch_references.py --id nvidia-linux-470.256.02 --download
python3 tools/fetch_references.py --id nvidia-linux-470.256.02 --extract-from downloads/NVIDIA-Linux-x86_64-470.256.02.run
```

The helper downloads only explicitly selected official HTTPS URLs, verifies the pinned hash, and optionally reads the `.run` tar payload in Python. It **never executes the installer**. Extraction creates a new local directory; links and special files are skipped, paths are checked, and extracted regular files have no execute bits. Driver files are for local research under NVIDIA's terms and remain excluded from Git.

The [official 470.256.02 checksum](https://download.nvidia.com/XFree86/Linux-x86_64/470.256.02/NVIDIA-Linux-x86_64-470.256.02.run.sha256sum) is `d6451862deb695bb0447f3b7cd6268f73e81168c10e2c10597ff3fa01349b1de`. Older entries whose `official_checksum_verified` is false are explicitly **locally observed hashes**, not asserted publisher signatures.

470.256.02 is a selected R470 comparison baseline, not a claim that every R470 improvement supports this exact mobile GTX 880M. The older 418.113 supported-device list explicitly named GTX 880M; support in the examined later list was not established. Linux APIs and binaries cannot simply be installed as macOS drivers.

## NVIDIA FreeBSD reference

Use the [official FreeBSD 470.256.02 directory](https://download.nvidia.com/XFree86/FreeBSD-x86_64/470.256.02/) and its [FAQ](https://download.nvidia.com/XFree86/FreeBSD-x86_64/470.256.02/README/faq.html). It is a separate native OS implementation useful for comparing common NVIDIA logic and OS adaptation. Obtain the package directly from NVIDIA, verify its published checksum when available, and extract only in an ignored local folder. This release does not bundle or automatically fetch it.

## Apple / macOS / restored Kepler components

Apple's driver binaries and SDKs are not open sourced by this project. Obtain macOS installers through [Apple's official download instructions](https://support.apple.com/102662), and Xcode from [Apple Developer](https://developer.apple.com/xcode/). Use your own licensed installation or authorized installer/package as the source for research.

For a machine where Kepler support is already restored, inspect it without modification:

```sh
python3 tools/inventory_local_driver.py > downloads-local-inventory.json
```

This prints selected bundle versions and SHA-256 values, omitting hostnames, serials and network configuration. It copies no binaries and changes nothing in `/System`. Keep the resulting inventory local. The reference `GeForceMTLDriver` executable hash was `2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054`. Similar version numbers alone are insufficient to establish binary compatibility.

To identify donor components rather than guessing a macOS/Linux version equivalence, consult OCLP's [Kepler patchset at the research revision](https://github.com/dortania/OpenCore-Legacy-Patcher/blob/d622cd5de86e5cb9a8c975c2809dbdbd2822c86e/opencore_legacy_patcher/sys_patch/patchsets/hardware/graphics/nvidia_kepler.py), [OCLP releases](https://github.com/dortania/OpenCore-Legacy-Patcher/releases), and [PatcherSupportPkg releases](https://github.com/dortania/PatcherSupportPkg/releases). Those are external provenance/recovery references; this repository does not mirror their payloads or invoke root patching. Follow the exact donor package and license applicable to your installation. Never substitute an unqualified binary for the installed working stack.

## Open source compiler references

| Project | Upstream | Pinned reference |
| --- | --- | --- |
| Mesa / NIR / NAK | `https://gitlab.freedesktop.org/mesa/mesa.git` | `96cb43121031992b85767f9c1be8f3f48e22b1d2` / 26.2.4 |
| OpenNVDA | `https://github.com/bdwithganesh/OpenNVDA.git` | `da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5` |
| envytools | `https://github.com/envytools/envytools.git` | `f102b82381f3f11cee113d16374c87091db039d9` |

Clone into `bridge/vendor/`, check out the exact revision, and verify `git rev-parse HEAD`. Historical tools expect directory names `mesa-26.2.4`, `OpenNVDA-<commit>`, and `envytools-<commit>`. Build directories may require reconfiguration for your machine. Review upstream licenses and the patches in `bridge/src/` before applying them. No complete upstream source tree or proprietary component is copied into the public repository.
