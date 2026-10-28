# NVIDIA RM device allocation and board identity

An on-disk comparison identifies how the installed GeForce image prepares its
RM device object and how a historical macOS CUDA sender prepares another
device-allocation request. Separately, two read-only registry observations
found a four-byte `rm_board_number` equal to zero on the unique PCI device
matching `10de:1198`. No RM client or device object was allocated in this work.

## Installed GeForce path

The GeForce file SHA-256 is
`44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3`.
`nvAccelerator::ContactResman` at `0x924c` obtains `rm_board_number` from a
registry entry, reads the first 32-bit word of its data and stores it at
accelerator offset `0x15f8`. In `nvVirtualAddressSpace::AllocDevice` at
`0x6a222`, this stored word becomes the first field of a locally initialized
parameter block. The routine calls `_NvRmAlloc` for class `0x80`, then, only
after success, for class `0x2080`. The kernel's class-0x80 call uses the same
root value as its first two handles and a separate device-object handle.
These are on-disk observations; the handle values and parameter flags used by
this driver are **not** a recipe for a new user client.

`CreateClientAndDevice` at `0x6a19c` calls `_NvRmAllocRoot` before an indirect
virtual call. The original `nvVirtualAddressSpace` vtable's corresponding
file-backed slot contains `0x6a222`, but the actual live object type and
indirect target have not been observed. A later teardown function contains a
conditional device `_NvRmFree`; its complete resource ownership and error
behavior are not qualified for an independent user client.

In the installed NVDAResman on-disk size routine, the branch for class `0x80`
sets the parameter length to **56 bytes when the parameter pointer is non-null**.
An old, unexecuted macOS CUDA sender also initializes a 56-byte candidate
parameter area, writes its chosen device index in the first word and submits a
class-0x80 allocation. Unlike the kernel path, the remaining fields in that
historical sender are zeroed. Its identity and generation differ from the
installed driver, so this does not establish compatibility or safe use.

The separately obtained NVIDIA [515.43.04 public `cl0080.h`](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/1739a20efc4acb55fd1dc53dcc66057b70c2613c/src/common/sdk/nvidia/inc/class/cl0080.h)
defines class `0x80` and a structure that compiles to 56 bytes in a CPU-only
x86-64 model using fixed-width definitions and the declared alignment. This
is a layout comparison, not proof that the newer open driver supports Kepler
or that every field has identical semantics in this older macOS binary.

## Registry observation

The [read-only inventory](../bridge/experiments/video_classlist/device_inventory.py)
uses `ioreg` to inspect `IOPCIDevice` properties without opening a connection.
Two independently executed observations selected exactly one matching PCI
device and returned the same four-byte value, `0`. They do not establish that
the registry object returned by the static `ContactResman` virtual call is
that precise PCI object, nor that an independent RM allocation would accept
the value. Registry IDs are instance-specific and can change after reboot.

## What remains

The public NVIDIA sender and installed kernel path differ in initialization,
and the exact device index, user-mode ownership, handle selection, two-level
copy, error handling and release still need live qualification. The old root
allocation/free witness has not been run on the changed profile. Do not copy
the kernel's handles or submit a device-allocation request based on this audit.
No loaded kernel memory, video execution or performance gain is claimed.

## Evidence and reproduction

The [static receipt](video-rm-device-identity-validation.json) pins the two
driver files, CUDA sender window, header and retained REA bundles. It checks
four GeForce bodies, selected RM relocations, a file-backed vtable slot and
the NVDA class-size table. The [two registry receipts](video-rm-board-observations.json)
record the two bounded observations. The old CUDA package was obtained and
extracted as described in [the control-route report](VIDEO_RM_CONTROL_PATH.md);
its expired package certificate did not pass the contemporary trust check.

```sh
R="$KP_LAB/bridge/results"
CUDA="$R/video-rm-emitter-progress-20261018/official-cuda-418.163/expanded/CUDAFramework.pkg/Payload/CUDA.framework/Versions/A/Libraries/libcuda_387.10.10.10_mercury.dylib"
python3 -B bridge/experiments/video_classlist/device_audit.py \
  --geforce /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --nvda /System/Library/Extensions/NVDAResman.kext/Contents/MacOS/NVDAResman \
  --cuda "$CUDA" --rea "$R/video-rm-device-path-rea-20261028-01.private.json" \
  --old-rea "$R/video-rm-abi-progress-20261018/NVDAUser-contract.private.json" \
  --header "$R/video-classlist-reference-20261028-01/cl0080-515.h" \
  --out /absolute/new-device-audit.json
python3 -B bridge/experiments/video_classlist/device_inventory.py --out /absolute/new-pci-observation.json
python3 -B -m unittest discover -s tests -p 'test_video_device*.py' -v
```

The auditor requires the exact private REA bundles and NVIDIA inputs by hash.
It compiles only a disposable CPU layout model. None of these commands opens
an RM connection, submits GPU work or modifies an installed component.
