# Video context access on the current driver profile

The current GTX 880M profile accepts a user-mode IOKit type-3 video-context
open and close. This repeats an earlier observation on a newer, explicitly
pinned profile. It does **not** submit a video command or prove that the video
engine decodes a frame.

Four fresh processes used one signed executable and the shared laboratory
reservation. The inventory found exactly one `nvAccelerator` under PCI vendor
`10de`, device `1198`. A deliberately wrong registry ID was refused before
opening anything. The two subsequent processes each opened the verified entry
with type 3, received a connection, and closed it: both IOKit statuses were 0.
All processes were terminal and their recorded lifetimes did not overlap.
The selected registry ID was `4294968416` on this boot; retrieve it afresh
rather than reusing it after a restart.

The host imports `IOServiceOpen` and `IOServiceClose`, with no
`IOConnectCall*` import. The program makes no explicit external method call,
GPU command or privileged request. Driver activity internal to open and close
was not traced. No decoded image, complete video-command ABI, RM client
allocation, firmware state or performance improvement is established.

The scope is the exact recorded x86_64 macOS 26.7.1 / 25G241 profile. Four
on-disk components and the kernel UUID were checked before and after each host;
loaded kext UUIDs were checked as build identifiers, not as hashes of running
kernel memory. The current GeForce hash is the one analyzed in
[the donor comparison](VIDEO_DONOR_COMPARISON.md). This new scoped witness does
not alter the old strict profile or authorize the prepared privileged RM test.
[Recorded evidence and hashes](video-context-current-validation.json).

Five offline mutations of a copied result—target, close status, process ID,
reservation state and source—were each rejected. The public oracle also has
portable synthetic positive and negative tests. The original, exploratory
first build and its four hosts are retained locally; the published evidence
below refers to the second build and its separate four-host cohort.

## Reproduce

Use an existing common lab reservation root and distinct new output paths. The
builder refuses a changed driver profile and requires the qualified macOS SDK;
no vendor files are bundled. The inventory itself performs no open. Extract the
registry ID from its independently verified `verification.stdout`, then use it
only while the selected boot and profile remain current. Every video run
rechecks the live class and PCI ancestry before opening.

```sh
python3 bridge/tools/video_context_current.py build --out /absolute/context-build
python3 bridge/tools/video_context_current.py run \
  --build /absolute/context-build --out /absolute/context-inventory \
  --reservation-root /absolute/common-lab/bridge --mode inventory
python3 bridge/tools/video_context_current.py run \
  --build /absolute/context-build --out /absolute/context-wrong \
  --reservation-root /absolute/common-lab/bridge --mode wrong-target
python3 bridge/tools/video_context_current.py run \
  --build /absolute/context-build --out /absolute/context-video-1 \
  --reservation-root /absolute/common-lab/bridge --mode video --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/video_context_current.py run \
  --build /absolute/context-build --out /absolute/context-video-2 \
  --reservation-root /absolute/common-lab/bridge --mode video --registry-id "$KP_LIVE_REGISTRY_ID"
python3 bridge/tools/audit_video_context_current.py \
  --inventory /absolute/context-inventory --wrong /absolute/context-wrong \
  --video /absolute/context-video-1 --repeat /absolute/context-video-2 \
  --out /absolute/new-context-audit.json
```

The `KP_LIVE_REGISTRY_ID` is the `gpu_registry_id` from the inventory oracle,
not a hard-coded identifier. The reservation coordinates project hosts; it is
not exclusive access to the GPU against WindowServer or unrelated processes.
