# Isolating the Metal queue failure to a shared-client lifecycle

**Follow-up:** [Delayed-close controls](VIDEO_SHARED_CLOSE_TIMING.md) create another queue while the extra type-6 connection is open and observe nil after it closes.

The [previous test](VIDEO_CONTEXT_COMPUTE.md) found that a new Metal queue could not be created after an experimental video context and type-6 shared client were associated and closed. This controlled follow-up separates the operations in eight new signed, nonoverlapping processes on the same pinned GTX and legacy AppleGVA test path.

| Operations between two queue-creation attempts | Runs | Queue before close | Queue after close |
| --- | ---: | --- | --- |
| No context or shared client | 2 | created | created |
| Type-6 shared client only | 2 | created | **nil** |
| Type-3 context and separate type-6 client, no association | 2 | created | **nil** |
| Type-3 context and type-6 client, associated | 2 | created | **nil** |

In each relevant case the explicitly opened connections and attempted association return zero, as do the explicit closes. The first queue is created while the type-6 connection is still open; the second attempt is made after it is closed. The shared-only case has **no type-3 open and no association**, so neither is necessary to reproduce this failure in the test. The no-client comparison creates and releases equivalent Metal objects but makes no type-3/type-6 open. The experiment does not distinguish the precise kernel/runtime event caused by the open, first queue's teardown, close, or their interaction; it does not establish whether the extra connection refers to Metal's own internal shared object.

The Metal device stays alive and matches the selected `nvAccelerator` registry ID `4294968416`. All tests deliberately skip GPU dispatch: 40,960 captured sentinel words and 320 guards match the independent audit. In the six failure cases the second queue is nil and no second buffer/capture exists. All eight hardware-required VideoToolbox creates still return `-12913` with zero images. The earlier GPU-execution control is separate; this cohort does not claim GPU execution, video decoding or a performance result.

The [audit](video-shared-isolation-validation.json) checks source and build hashes, signed terminal process receipts, nonoverlap, actual choices and assets, IOKit result counts, queue outcomes and raw sentinel data. Its `EXPECTED_FAILURE_CONFIRMED` status means the observed Metal compatibility failure was detected; it is **not** product success. Two negative unit tests reject a misclassified queue failure or corrupted capture; sixteen related provider-auditor tests also pass. A cooperative reservation coordinates the test processes, not WindowServer. The selected old AppleGVA and policy/dependency substitutions remain process-local; the historical Sierra provider is not called, and no private video selector is sent.

Until the shared-client ownership and failure are understood, do not use the experimental associated lease in a process that must continue creating Metal queues. Further tests should keep the extra type-6 connection open through both queue attempts, then isolate its close and inspect the independently observed Metal shared-client identity. No installed driver, macOS framework, OCLP or firmware was modified.

## Re-audit the recorded cohort

These commands need the exact private lab, pinned build/profile and boot-specific registry ID. The auditor checks the frozen build and does not silently re-pin another one; no vendor binary or raw buffer is distributed.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
EXP=bridge/experiments/video_shared_isolation
python3 "$EXP/audit.py" --build "$R/video-shared-isolation-build-20261028-01" \
  --out "$R/video-shared-isolation-reaudit-new.json" \
  --hosts "$R/video-shared-isolation-none-20261028-01" "$R/video-shared-isolation-shared-20261028-01" \
  "$R/video-shared-isolation-pair-20261028-01" "$R/video-shared-isolation-attach-20261028-01" \
  "$R/video-shared-isolation-attach-20261028-02" "$R/video-shared-isolation-pair-20261028-02" \
  "$R/video-shared-isolation-shared-20261028-02" "$R/video-shared-isolation-none-20261028-02"
python3 -m unittest discover -s tests -p 'test_video_shared_isolation.py' -v
```
