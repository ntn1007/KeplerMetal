# Shared video-client prerequisite: observed refusal

A bounded test attempted to open IOKit user-client type 6 on the already
qualified `nvAccelerator` service, without opening a video context or calling
`IOConnect*`. On the recorded profile, two fresh processes each received
`0xe00002c7` and no connection; there was consequently no connection to close.
Apple's [IOReturn.h](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/iokit/IOKit/IOReturn.h)
names this `kIOReturnUnsupported`. **This is an observed refusal under these
conditions**, not proof that the GPU or the client can never be used.

The common lab reservation was held for each fresh signed process. The
inventory found one PCI `10de:1198` `nvAccelerator`; a wrong-ID negative
control opened nothing. Both real attempts completed without a kill, and the
reservation recorded each as terminal. The executable imports
`IOServiceOpen` and `IOServiceClose`, not `IOConnect*`. Four on-disk file
hashes and loaded kext and kernel UUIDs were checked before and after each
process. This checks loaded build identifiers, not the bytes of running kernel
memory. The local [cohort audit](video-shared-refusal-validation.json) verifies
that all four captures came from the same build, signed executable and live
registry ID. No video command or decode was attempted; internal driver effects
were not traced.

The original strict oracle expected a successful open and exited 1 on each
refusal. Those results and errors are retained. The separate refusal audit
checks those failures, requires the exact observed error, and reports
`audit_status=PASS` **and** `capability_status=REFUSED`. It does not turn the
failed opens into a supported feature.

## What the NVIDIA factory adds

The pinned GeForce file's `nvAccelerator::newUserClient` at `0xd328` has a
special type-6 branch. Static Ghidra analysis and symbol/instruction checks
show calls to `FindDeviceForTask` for several categories, reuse or creation of a
shared client, and an `0xe00002c9` return on the path where no suitable device
is found. The exact lookup categories and resource ownership are private
implementation details, and the branch actually taken during the two attempts
was not observed. In particular, the observed `0xe00002c7` is **different**
from that static missing-device error: a missing device is a hypothesis, not a
proven cause of these refusals. Other kernel or driver paths may return the
observed code.

A useful next investigation is to establish how an ordinary, unmodified Metal
client creates the relevant same-task device and compare the ordering with this
isolated attempt. A bounded public-API witness may then test that hypothesis;
it must identify the same GPU, retain the public Metal objects during the
observation, use the common reservation, and preserve failure evidence. A
successful client open would still not prove safe association, buffer ABI,
decoding, or hardware video execution.

## Reproduction

The lab captures are local, immutable evidence. The signed executables and
vendor binaries are not distributed. The first four commands use fresh output
paths, a current registry ID from the inventory, and the existing reservation
root. The two `shared` commands were expected by the original strict oracle to
succeed; for the observed refusal they exit nonzero after saving the result,
manifest and strict-oracle error. Do not ignore a different infrastructure
failure or repeat after an unresolved reservation.

```sh
python3 bridge/tools/video_shared_current.py build --out /absolute/shared-build
python3 bridge/tools/video_shared_current.py run --build /absolute/shared-build --out /absolute/shared-inventory --reservation-root /absolute/lab/bridge --mode inventory
python3 bridge/tools/video_shared_current.py run --build /absolute/shared-build --out /absolute/shared-wrong --reservation-root /absolute/lab/bridge --mode wrong-target
python3 bridge/tools/video_shared_current.py run --build /absolute/shared-build --out /absolute/shared-first --reservation-root /absolute/lab/bridge --mode shared --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_shared_current.py run --build /absolute/shared-build --out /absolute/shared-repeat --reservation-root /absolute/lab/bridge --mode shared --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/audit_video_shared_refusal.py --inventory /absolute/shared-inventory --wrong /absolute/shared-wrong --first /absolute/shared-first --repeat /absolute/shared-repeat --out /absolute/new-refusal-audit.json
python3 bridge/tools/video_shared_factory_evidence.py --geforce /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce --capture "$KP_LAB/bridge/results/video-shared-factory-20261027/0xd328.private.json" --out /absolute/new-factory-audit.json
python3 -m unittest discover -s tests -p test_video_shared_current.py -v
```

`KP_LIVE_REGISTRY_ID` is taken from the new inventory oracle; it is not stable
across boots. The static REA capture contains decompiled vendor code and stays
in the local lab. Its [public identity and hashes](video-shared-factory-validation.json)
are checked against the exact pinned GeForce file. No system driver, OCLP,
firmware or protected configuration was changed.
