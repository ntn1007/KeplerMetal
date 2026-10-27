# Video context and shared-client association

The GTX 880M's qualified profile now accepts a bounded association of the
previously tested type-3 video context with a type-6 shared connection. In two
fresh processes, `IOConnectAddClient(context, shared)` returned zero and both
connections subsequently closed with zero status. Two additional processes
opened and closed the same kinds of connection without associating them.
Inventory and wrong-target controls opened neither connection. All six hosts
were signed, serialized under the common laboratory reservation, and ran the
same frozen executable.

The host keeps an ordinary Metal device alive in its own process, checks the
Metal device and `nvAccelerator` against the same NVIDIA `10de:1198` PCI
ancestor, and refuses ambiguous targets. It opens type 3 and then type 6,
requires two distinct returned port names, calls the public
[IOConnectAddClient API](https://developer.apple.com/documentation/iokit/1514609-ioconnectaddclient)
only in `attach` mode, and closes the context before the shared connection.
Its executable imports `IOConnectAddClient` but no `IOConnectCall*` function;
it sends no explicit video selector or GPU command. Metal's and the driver's
internal activity were not traced. The five pinned on-disk components and the
kernel/loaded-kext UUID profile are checked before and after every host; UUIDs
identify builds rather than bytes of running kernel memory. The reservation
coordinates lab processes, not WindowServer or every other GPU client.

[Recorded cohort audit](video-context-association-validation.json) captures
process identities, fingerprints, ordering and statuses. A zero return is
**evidence that the association request was accepted** on this profile, not a
runtime trace of the internal object or proof of cleanup under all conditions.
The test does not establish GPU video execution, valid buffer contents,
complete ownership semantics, or decode correctness. Only the context-first
close order and successful paths were exercised. The two port names being
distinct does not by itself prove distinct underlying kernel objects. The native
CF-wrapper candidates use `IOConnectRelease`; see the later
[lifetime analysis](VIDEO_BUFFER_LIFETIME.md).

## Start-path static evidence

On the pinned files, the NVIDIA `nvVideoContext::contextStart` at `0x6832e`
branches through the parent video-context vtable to `0x3a016`; the parent in
turn calls the inherited `IOAccelContext2::contextStart` at `0x7a9c`. That
routine initializes bookkeeping and resources, and one recorded failure path
calls the inherited `contextStop` at `0x7eea`. The static evidence and its
capture hashes are [recorded separately](video-context-start-validation.json).
The branch actually executed in the live test was not traced; this does not
qualify every failure or close order. Previous [ownership analysis](VIDEO_RESOURCE_OWNERSHIP.md)
describes the corresponding stop and shared-reference paths.

The next step is to establish the resource-buffer contract and release
semantics before any selector invocation. Do not infer valid payloads from the
8-byte input size, and do not submit unqualified video commands to the display
GPU.

## Reproduction

Use fresh output directories and the shared lab reservation. Get the current
accelerator registry ID from the inventory result; it can change after a boot.
The audit expects inventory, wrong target, pair, attach, pair, attach in that
order. A refused association is preserved as an observation by the individual
oracle, but this specific audit accepts only the recorded successful cohort.

```sh
python3 bridge/tools/video_context_association.py build --out /absolute/association-build
python3 bridge/tools/video_context_association.py run --build /absolute/association-build --out /absolute/inventory --reservation-root /absolute/lab/bridge --mode inventory
python3 bridge/tools/video_context_association.py run --build /absolute/association-build --out /absolute/wrong --reservation-root /absolute/lab/bridge --mode wrong-target
python3 bridge/tools/video_context_association.py run --build /absolute/association-build --out /absolute/pair-1 --reservation-root /absolute/lab/bridge --mode pair --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_context_association.py run --build /absolute/association-build --out /absolute/attach-1 --reservation-root /absolute/lab/bridge --mode attach --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_context_association.py run --build /absolute/association-build --out /absolute/pair-2 --reservation-root /absolute/lab/bridge --mode pair --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_context_association.py run --build /absolute/association-build --out /absolute/attach-2 --reservation-root /absolute/lab/bridge --mode attach --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/audit_video_context_association.py --run /absolute/inventory --run /absolute/wrong --run /absolute/pair-1 --run /absolute/attach-1 --run /absolute/pair-2 --run /absolute/attach-2 --out /absolute/association-audit.json
python3 bridge/tools/video_context_start_evidence.py --ioaccel /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2 --geforce /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce --ge-capture "$KP_LAB/bridge/results/video-nvidia-start-20261027/0x6832e.private.json" --io-capture "$KP_LAB/bridge/results/video-parent-start-20261027/0x3a016.private.json" --prior-rea "$KP_LAB/bridge/results/video-command-contract-progress-20261018/IOAccel-command-contract-final.private.json" --out /absolute/context-start-audit.json
python3 -m unittest discover -s tests -p test_video_context_association.py -v
```

REA captures containing vendor decompilation remain local; only their hashes,
evidence identifiers and source-only checkers are published. No system driver,
OCLP, firmware or protected configuration was changed.
