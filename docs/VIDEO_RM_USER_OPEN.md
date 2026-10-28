# Current-profile unprivileged NVIDIA port open

Two signed UID 501 processes attempted one `IOServiceOpen` each on the
previously observed `NVDA,Display-A` service, with client type `0x80000000`.
Both returned `0xe00002c7` and no connection. A compiled check against the
installed SDK identifies that value as `kIOReturnUnsupported`. Neither process
sent an RM method, allocated an RM root/device object or dispatched GPU work.
This is an observed return, **not** an established reason for the refusal.

The selected NVDA registry ID was `4294968425` for this boot. Each process
rechecked the UUID, five pinned on-disk system files, three IOKit regions in
its own process, the device PCI properties, the exact service ID and its
immediate `IONDRVDevice` / `NVDA,Display-A` parent. Each inherited the shared
cooperative lab reservation. These checks do not prove loaded NVIDIA kernel
bytes match the on-disk files or cover other system clients.

One wrong-ID and one wrong-code-hash control refused before opening; a fifth
signed process launched without the lease refused before inspecting or
opening the service. All four leased processes exited normally, without a
kill request, and their reservation states were terminal. No connection was
returned, so no close call was needed in either open attempt. The runner
waits for the child without an automatic kill; an uncertain child outcome
keeps the reservation unresolved.

On the earlier system profile, a user-mode open also returned `0xe00002c7`,
whereas a separately authenticated administrator open and close succeeded.
Those historical observations are useful context, but do not establish the
cause of the current refusal or prove administrator access still works after
the [profile changed](VIDEO_PROFILE_DRIFT.md). This work does not invoke sudo,
reuse cached authentication, or alter the historical privileged witness.

## Evidence and reproduction

The [receipt](video-rm-user-open-validation.json) checks the exact source,
signed binaries, build, runner, four leased manifests and a no-lease control.
The decoded SDK constant comes from a separate disposable CPU compilation.
The [probe source](../bridge/experiments/video_rm_profile/open_probe.mm)
contains only bounded IOKit open/close and refusal controls; it has no RM
method submission. No proprietary driver code or binary is distributed.

```sh
R="$KP_LAB/bridge/results"
python3 -B bridge/experiments/video_rm_profile/open_audit.py \
  --source bridge/experiments/video_rm_profile/open_probe.mm \
  --runner bridge/experiments/video_rm_profile/open_runner.py \
  --build "$R/video-rm-open-uid-build-20261028-01" \
  --runs "$R/video-rm-open-uid-wrong-id-20261028-01" \
         "$R/video-rm-open-uid-wrong-code-20261028-01" \
         "$R/video-rm-open-uid-valid-20261028-01" \
         "$R/video-rm-open-uid-valid-20261028-02" \
  --no-lease "$R/video-rm-open-uid-no-lease-20261028-01" \
  --out /absolute/new-user-open-audit.json
```

Re-running the experiment requires a freshly identified service ID, a fresh
build/output location and review of the exact pinned profile. The historical
auditor intentionally accepts only the recorded cohort. A successful port
open alone would not prove RM object allocation, class-list contents, video
decoding or a performance gain.
