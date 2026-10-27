# Shared video client after same-process Metal initialization

The isolated type-6 opening [previously failed](VIDEO_SHARED_CLIENT.md). A new
comparison demonstrates a working prerequisite on the recorded profile:

| Same-process setup, kept alive during open | Results, two fresh processes each |
| --- | --- |
| No Metal device | Both refused with `0xe00002c7` |
| Matching Metal device | Both opened and closed successfully |
| Matching Metal device and command queue | Both opened and closed successfully |

`MTLCopyAllDevices` supplied the retained device. The host finds the target
`nvAccelerator` and checks that the Metal device and that service have the
**same PCI ancestor**, identified as NVIDIA `10de:1198`. Only then can the
host call `IOServiceOpen(..., type=6)`. A command queue is made only in the
third condition; no command buffer is created or submitted by the host. The
queue and device array remain alive until after the extra connection closes.
Inventory and wrong-target controls open no connection and perform no Metal
enumeration. The two repetitions were serialized in a different order, with
one signed executable, separate process identities and the same boot-time
registry identities.

This is evidence that a same-process public Metal initialization changes the
outcome. It does **not** identify which internal Metal/driver call caused that
change, prove an `IOConnectAddClient` association, qualify a buffer ABI, or
show hardware video decode. A returned connection does not establish its
object's identity by itself; the type-6 factory interpretation is based on
separate static analysis. Metal may perform internal driver activity while
creating its objects; this witness traces only explicit calls made by its own
host.

The five pinned on-disk binaries include the current `GeForceMTLDriver` SHA-256
`e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645`, in
addition to the four kernel extensions from the earlier witness. The runner
checks those hashes, the kernel UUID and loaded kext UUIDs before and after each
process. Loaded UUIDs identify builds, not the bytes in kernel memory. The
common lab lock serializes participating lab hosts, not WindowServer or all
other GPU processes. [Recorded audit and raw-capture hashes](video-shared-metal-validation.json).

The next step is to qualify the complete start, failure and teardown semantics
of associating a type-3 context with this shared connection. A context open and
a shared-client open separately do not yet qualify that association. Preserve
an ordinary Metal object while investigating its lifetime; do not send video
selectors or arbitrary command packets until their ABI and resource ownership
are established.

## Reproduction

The audit accepts the following order: inventory, wrong target, direct, device,
queue, queue, direct, device. Use a fresh build, a new output directory for each
host and the same shared laboratory reservation. Obtain the current accelerator
registry ID from the first host's `verification.stdout`; do not reuse the
recorded value after a restart. Each `run` prints `OPEN_REFUSED` or
`OPEN_CLOSED` as an observed outcome; `verification=PASS` means the evidence is
internally consistent, not that a refused open succeeded. Stop if any host is
unresolved or a profile/identity guard fails.

```sh
python3 bridge/tools/video_shared_metal.py build --out /absolute/metal-shared-build
python3 bridge/tools/video_shared_metal.py run --build /absolute/metal-shared-build --out /absolute/inventory --reservation-root /absolute/lab/bridge --mode inventory
python3 bridge/tools/video_shared_metal.py run --build /absolute/metal-shared-build --out /absolute/wrong --reservation-root /absolute/lab/bridge --mode wrong-target
python3 bridge/tools/video_shared_metal.py run --build /absolute/metal-shared-build --out /absolute/direct-1 --reservation-root /absolute/lab/bridge --mode direct --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_shared_metal.py run --build /absolute/metal-shared-build --out /absolute/device-1 --reservation-root /absolute/lab/bridge --mode device --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_shared_metal.py run --build /absolute/metal-shared-build --out /absolute/queue-1 --reservation-root /absolute/lab/bridge --mode queue --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_shared_metal.py run --build /absolute/metal-shared-build --out /absolute/queue-2 --reservation-root /absolute/lab/bridge --mode queue --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_shared_metal.py run --build /absolute/metal-shared-build --out /absolute/direct-2 --reservation-root /absolute/lab/bridge --mode direct --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_shared_metal.py run --build /absolute/metal-shared-build --out /absolute/device-2 --reservation-root /absolute/lab/bridge --mode device --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/audit_video_shared_metal.py --run /absolute/inventory --run /absolute/wrong --run /absolute/direct-1 --run /absolute/device-1 --run /absolute/queue-1 --run /absolute/queue-2 --run /absolute/direct-2 --run /absolute/device-2 --out /absolute/new-audit.json
python3 -m unittest discover -s tests -p test_video_shared_metal.py -v
```

No system driver, OCLP, firmware or protected configuration was changed.
