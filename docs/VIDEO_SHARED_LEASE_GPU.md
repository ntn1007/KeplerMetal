# Associated video lease with guarded shared-client release

This follow-up applies the existing `VideoContextLease` to a selected GTX service while a genuine Metal device and buffer remain alive. A process-local experimental backend opens a type-3 video context, opens a type-6 client, associates them using `IOConnectAddClient`, closes the type-3 context and releases the extra shared-client reference. The backend is part of this witness; it is **not** installed into the existing reusable native backend, and its pinned assumptions do not qualify arbitrary applications.

The local guard requires that the type-6 result has the same port name as the Metal-owned shared connection, that reflexive and cross-object `IOObjectIsEqualTo` checks pass, and that its successful open increments the local Mach send-right user-reference count by exactly one. It also checks immediately before release that the count has not changed following type-3 closure. Unqualified outputs are not forwarded to association; uncertain acquired references are deliberately left for process exit. The checks do not synchronize other threads, prove general kernel ownership, or make the decision free of a time-of-check/time-of-use race. The witness controls its own sequence and retains the Metal objects. Reference counts are user references, not kernel retain counts.

## Result

The [independent seven-process audit](video-shared-lease-gpu-validation.json) reports `PASS_BOUNDED_ASSOCIATED_LEASE_RELEASE`:

- Two guarded-release processes successfully open, associate and close the context and release the extra shared reference; a new Metal queue and GPU dispatch succeed afterwards. The CPU oracle independently verifies **8,192 GPU-written words** in these two processes.
- Two controls use the same association but close the extra shared client with `IOServiceClose`; both return success from teardown yet cannot create the later Metal queue. The failure is expected and preserved.
- One no-lease Metal control checks 4,096 more GPU words. Two no-dispatch controls preserve 8,192 sentinel words; the audit checks 160 boundary guard words. The full cohort therefore contains 12,288 correct GPU words, including the control.
- The send-right counts are 1 before extra open, 2 after open and immediately before shared release, and 1 afterward in these cases. The exact build inputs have SHA-256 `248195636c91ea1f0cbd0718c365496a79946aa1685cc189aad656808bc377f1`.

No explicit video selector or decoder is exercised, and no hardware video execution or performance improvement is proved. These tests call neither the legacy AppleGVA provider nor the Sierra provider. This is not a system-wide driver fix. The prior [video lease warning](VIDEO_CONTEXT_LEASE.md) remains in force; concurrent clients, failed opens with ambiguous ownership, different GPUs, profiles and application lifetimes require independent qualification. Driver/framework internals and WindowServer are not exhaustively observed. No macOS, NVIDIA driver, OCLP or firmware was modified.

## Re-audit

This checks retained evidence rather than rerunning GPU jobs. It needs the private lab and exact pinned build, sources and profile:

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
python3 bridge/experiments/video_shared_lease_gpu/audit.py \
 --build "$R/video-shared-lease-gpu-build-20261028-01" \
 --out "$R/video-shared-lease-gpu-reaudit-new.json" --runs \
 "$R/video-shared-lease-gpu-release-1-20261028" "$R/video-shared-lease-gpu-observe-1-20261028" \
 "$R/video-shared-lease-gpu-close-1-20261028" "$R/video-shared-lease-gpu-negative-1-20261028" \
 "$R/video-shared-lease-gpu-release-2-20261028" "$R/video-shared-lease-gpu-negative-2-20261028" \
 "$R/video-shared-lease-gpu-close-2-20261028"
xcrun clang++ -std=c++17 -Wall -Wextra -Werror -fsanitize=undefined \
 bridge/experiments/video_context_lease/VideoContextLease.cpp bridge/experiments/video_context_lease/test.cpp \
 -o /tmp/kepler-video-lease-test && /tmp/kepler-video-lease-test
python3 -m unittest discover -s tests -p 'test_video_provider_*.py' -v
```
