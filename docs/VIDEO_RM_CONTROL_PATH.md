# Video research: NVIDIA RM control route

The prior [class-list audit](VIDEO_CLASSLIST_PROVENANCE.md) located two kernel
`NvRmControl` calls for `0x800201`. This follow-up connects the **outer** RM
control command to a historical NVIDIA macOS sender and the installed on-disk
receiver. It is static evidence, not a live class-list query or a hardware-video
implementation.

## What the files show

The separately obtained, unexecuted CUDA 418.163 package contains a historical
`libcuda_387.10.10.10_mercury.dylib`, SHA-256
`fb646845ca1f885f71cc5394c059a57aef36fdf32b1029ad891c372090c9b9f4`.
An analyst-selected 174-byte window at `0x22bfc4` writes outer command `0x702a`
and logical length 32, makes a call through the previously verified
`IOConnectCallStructMethod` import stub with selector 1, and uses a 184-byte
input and output capacity. It places three 32-bit arguments at payload offsets
0, 4 and 8, a 64-bit pointer at offset 16, and a 32-bit length at offset 24;
the successful transport path reads status at payload offset 28. The window's
observed first and final instructions do not independently establish complete
function boundaries or compatibility with Tahoe.

The installed on-disk NVDAResman image, SHA-256
`36396eaecd68ddbb0482f019f38ce55d01b10379ca829da7f19b3bd8f3e26808`,
contains `_NvRmControl` at `0x724f0`. It constructs that same outer command,
length, field positions and status offset for its five arguments before
calling the internal dispatcher at `0x708d0`. The class-list command `0x800201`
is the **inner** control command; it is not the IOKit selector or the outer
`0x702a` operation. This corresponds structurally to the sender, without
proving that the historical user client can make this particular request.

At the dispatcher's jump-table case for `0x702a`, `0x70b7b` checks a 32-byte
logical payload, then follows client/task-related checks before selecting the
internal or user route. The specific `0x600d600d` marker selects the internal
route; the other branch calls `0x32e88`, which passes a value of one to
`0x32238`. That function forwards the five fields and this flag through
`0x441fb` to `0x44215`. The analysis of `0x44215` shows additional validation
and indirect dispatch, but does **not** establish how `0x800201` copies an
embedded class-list pointer between address spaces. Ghidra reports removed
unreachable blocks in a downstream lookup; its simplified pseudocode is not
enough to establish all dispatch behavior.

Consequently, the candidate route needs an authenticated, properly owned RM
client and device context, a qualified handling of both levels of pointers,
correct cleanup, and current-profile validation. None is inferred from this
static comparison. The old administrator experiment opened and closed a port
only; the prepared allocation/free witness remains unexecuted on the changed
[system profile](VIDEO_PROFILE_DRIFT.md). Do not send `0x702a` or `0x800201` to
the display GPU on the basis of this audit.

## Evidence and reproduction

[Validation receipt](video-rm-control-path-validation.json) pins the two images,
six receiver function bodies, the CUDA window, two private REA bundles, the
`0x702a` jump-table cell and selected direct call/jump targets. The CUDA import
stub was separately checked against the original Mach-O in the retained
October 18 CUDA audit. The new REA/Ghidra analysis covers the installed file;
the original dispatcher dossier comes from the earlier bundle with the same
NVDAResman hash. No loaded kernel memory was inspected. Proprietary files,
disassembly and private bundles are not redistributed.

The historical archive is obtained from [NVIDIA's CUDA 418.163 macOS page](https://www.nvidia.com/en-gb/drivers/cuda/418_163/macosx-cuda-418_163-driver/)
and extracted without installing or executing it. Its package signature check in
the retained lab record returned an expired signing certificate, so present-day
signature trust was not established. The sender is a different generation from
the installed macOS driver.

Set `KP_LAB` to the existing laboratory root and provide the separately retained
bundles; output must be a new path. The verifier is CPU-only and reads the files:

```sh
R="$KP_LAB/bridge/results"
CUDA="$R/video-rm-emitter-progress-20261018/official-cuda-418.163/expanded/CUDAFramework.pkg/Payload/CUDA.framework/Versions/A/Libraries/libcuda_387.10.10.10_mercury.dylib"
python3 -B bridge/experiments/video_classlist/control_audit.py \
  --nvda /System/Library/Extensions/NVDAResman.kext/Contents/MacOS/NVDAResman \
  --cuda "$CUDA" \
  --old-rea "$R/video-rm-abi-progress-20261018/NVDAUser-contract.private.json" \
  --new-rea "$R/video-rm-control-rea-20261028-02.private.json" \
  --out /absolute/new-control-audit.json
python3 -B -m unittest discover -s tests -p 'test_video_control_audit.py' -v
```

Recreating the second bundle requires REA 6.4.0 / Ghidra 12.1.4 and the same
input and analysis profile; the exact retained bundle hash is required by this
auditor. A newly generated bundle with different metadata requires independent
review rather than silently changing the pin. The first bundle was retained
from the earlier RM transport analysis. The auditor checks these records and
original bytes; its passing result is not a live runtime trace.
