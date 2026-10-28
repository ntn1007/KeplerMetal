# Submitted Metal command across guarded video-lease teardown

A bounded experiment on the GTX 880M submits a Metal command buffer before opening, associating and releasing the experimental type-3 video context and its aliased type-6 client. A shared event initially at zero gates the command buffer. The host observes its status and unchanged output before and after the lease lifecycle, then signals the event and waits for completion. The private shared-object observer, guarded backend, device, resource and buffer remain confined to the test process.

This tests a **submitted, incomplete** command across the lifecycle. It does not prove that GPU instructions were already executing while the context was closed: the recorded Metal status was `committed` (2), and the event blocked subsequent work. It also does not establish safety with concurrent unrelated Metal threads, general reference ownership, video-engine use, a production driver fix or improved performance. [The existing backend's coordination and TOCTOU limitations remain](VIDEO_GUARDED_BACKEND.md).

## Results

The [seven-process audit](video-lease-pending-validation.json) checks pinned sources and build, signatures, terminal nonoverlapping reservations, object identity, status, event values, negative controls and raw captures. In each process, the pre- and post-lifecycle observations show status 2, event value 0, no changed output words and no watchdog firing. Afterwards the host signals the event, the command reaches status 4 (completed), and the independent CPU oracle checks the raw result.

- Two guarded-lease processes each produce 4,096 correct GPU values after release: **8,192** total.
- Two no-lease controls produce another 8,192 correct values. The aggregate is **16,384**, including controls.
- Two lease and one no-lease no-dispatch controls preserve 12,288 sentinel words. All 224 guard words across the seven captures remain intact.
- The associated lease succeeds and the send-right user-reference counts are 1 before opening, 2 after opening and before release, and 1 after release. These are local user-reference counts, not kernel retain counts.

The test schedules a two-second watchdog to signal the event if the normal path stalls and uses a `finally` block to signal on exceptional exit. The watchdog did not fire in the qualified cohort; this cohort does not independently qualify its emergency path. No explicit video selector or decoding is exercised, and driver/framework internals are not exhaustively traced. No macOS, OCLP, driver or firmware component was changed.

## Re-audit and verifier tests

This re-reads retained evidence; it does not run a new GPU workload. It requires the private lab, the exact frozen build and current source snapshot:

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
python3 bridge/experiments/video_lease_pending_gpu/audit.py \
 --build "$R/video-lease-pending-build-20261028-01" \
 --out "$R/video-lease-pending-reaudit-new.json" --runs \
 "$R/video-lease-pending-control-1-20261028" "$R/video-lease-pending-pending-1-20261028" \
 "$R/video-lease-pending-control-negative-1-20261028" "$R/video-lease-pending-pending-negative-1-20261028" \
 "$R/video-lease-pending-pending-2-20261028" "$R/video-lease-pending-control-2-20261028" \
 "$R/video-lease-pending-pending-negative-2-20261028"
python3 -m unittest discover -s tests -p 'test_video_lease_pending_gpu.py' -v
```

The build-input SHA-256 is `34df9fb140ab09155f0ca2c78ee72364bc078ef3b948b1a95cdd107509f9ed9a`. The verifier tests intentionally corrupt stage status, watchdog state, signal, data and guards; an anomalous negative control is not silently accepted.
