# Metal queue creation around a type-6 close

The [type-6 isolation](VIDEO_SHARED_ISOLATION.md) found a Metal queue failure after an extra shared client was opened and closed. This follow-up moves the close between three queue-creation attempts in a controlled, own-process legacy AppleGVA test. The same pinned GTX Metal device remains alive throughout; no video context, video selector or GPU dispatch is used.

| Sequence | Runs | First queue | Middle queue | Final queue |
| --- | ---: | --- | --- | --- |
| No extra type-6 client | 2 | created | created | created |
| Open type 6; close before middle attempt | 2 | created | **nil** | **nil** |
| Open type 6; close after middle attempt | 2 | created | created | **nil** |

In the delayed-close cases, both successful queue attempts occur while the extra client is open. The last attempt occurs after `IOServiceClose` returns zero and produces nil. The early-close cases fail at both attempts after close, while the no-client controls continue to create queues. These results identify the transition at which the behavior changes under this sequence; they do not identify the internal cause, establish the identity of Metal's own client, or show persistence beyond the process. Successful queue creation is not proof of a successful GPU dispatch.

All six requests retain the explicitly selected legacy AppleGVA path and the prior process-local policy/dependency substitutions. The test gate returns 14 instead of invoking the NVIDIA Sierra provider. Hardware-required VideoToolbox creation still returns `-12913` and zero images. All tests skip GPU dispatch; the independent [audit](video-shared-timing-validation.json) checks 49,152 captured sentinel words and 384 guard words, frozen build and sources, signed terminal nonoverlapping receipts, actual input choices and IOKit statuses. `EXPECTED_FAILURE_CONFIRMED` means the compatibility failure was reproduced, not that the product scenario passed. Fifteen related shared-client audit tests pass.

Do **not** treat leaving the extra client open indefinitely as a fix: that can retain resources and does not qualify teardown or real video work. The next useful step is to identify whether the extra type-6 right and Metal's internally owned shared client refer to the same underlying object, then design a lifecycle that preserves Metal's ownership. No driver, OCLP, firmware or framework was modified; the cooperative reservation does not exclude WindowServer.

## Re-audit the exact recorded build

This requires the local private lab, exact pinned binaries and boot-specific GPU registry ID; no proprietary binaries or raw captures are published. Rebuilds and changed profiles need independent qualification.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
EXP=bridge/experiments/video_shared_close_timing
python3 "$EXP/audit.py" --build "$R/video-shared-timing-build-20261028-01" \
  --out "$R/video-shared-timing-reaudit-new.json" \
  --hosts "$R/video-shared-timing-none-20261028-01" "$R/video-shared-timing-early-20261028-01" \
  "$R/video-shared-timing-hold-20261028-01" "$R/video-shared-timing-hold-20261028-02" \
  "$R/video-shared-timing-early-20261028-02" "$R/video-shared-timing-none-20261028-02"
python3 -m unittest discover -s tests -p 'test_video_shared*.py' -v
```
