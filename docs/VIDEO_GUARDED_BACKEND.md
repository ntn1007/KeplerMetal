# Experimental guarded video-lease backend

`GuardedAliasBackend` extracts the [associated-lease witness](VIDEO_SHARED_LEASE_GPU.md) into a transport-independent, reusable test component. It supplies callbacks to the existing `VideoContextLease`; callers supply trusted, nonthrowing operations and a borrowed Metal shared-connection handle. The hardware test uses explicit IOKit operations and a process-local, profile-pinned observer to obtain that handle. This adapter does not discover or retain the Metal object itself. It does not install a driver, replace the earlier native backend, or provide a general application integration.

It refuses an unqualified shared open and an inconsistent pre-release reference count. If closing the context fails, it refuses to release the extra shared reference; if a shared release fails, it does not retry because ownership is uncertain. A failed open that returns a nonzero output is recorded as ambiguous and is not treated as owned. Unqualified or uncertain references can remain until process exit; that deliberate leak is not suitable as a general recovery policy. If the reference count cannot be checked or differs after a successful release, the operation is reported as a failure even though the release has already happened.

## Synchronization contract

The caller must keep the borrowed Metal object alive and serialize the *entire* lifecycle, including every other participant capable of affecting its shared connection and references. The guard itself contains **no mutex**. In particular, a caller-owned mutex does not prevent unrelated Metal/framework or driver activity, and the check and release remain subject to a time-of-check/time-of-use race. The injected callbacks must correspond to the qualified profile; the `releaseShared` callback must really use the chosen release operation, not an arbitrary close. The test's explicit-close callback is only an expected-failure comparison. A count of Mach user references is not a kernel retain count. These requirements and unknowns prevent treating this component as generally safe for arbitrary applications.

## Validation

- On the iMac, pure CPU tests compiled with UndefinedBehaviorSanitizer cover a successful lease; open failures with ambiguous output; alias mismatch and failed identity checks; count errors and changes; association failure; context-close failure; release failure and non-retry; and a failed postcondition.
- On the MacBook M1 Max, the same six source files were copied over authenticated SSH and their SHA-256 values compared. ThreadSanitizer passed the CPU mock tests, including 8 cooperative threads and 1,600 lifecycles protected by the same mutex. [Evidence](video-guarded-backend-cpu-validation.json). This is neither a Kepler GPU test nor proof about unsynchronized framework or kernel activity. On the iMac, ThreadSanitizer exited with `SIGILL` (132), as did an independently compiled empty control; the cause is unknown.
- The [seven-process GTX audit](video-guarded-backend-gpu-validation.json) checks frozen sources and signed binaries, serialized process intervals, identity, raw GPU output and controls. Two guarded-release runs each produce 4,096 correct GPU words after context association and teardown; a separate no-lease control contributes 4,096 more. Two explicit-close controls reproduce the later queue failure, and two no-dispatch controls preserve 8,192 sentinel words. In these cases the user-reference counts follow 1 → 2 → 1.

No video decoding, general application support, Metal 3/4 conformance or performance improvement is established. No macOS, OCLP, driver or firmware component was changed. The ordinary native lease backend remains unqualified for continued Metal use.

A [follow-up witness](VIDEO_LEASE_PENDING_GPU.md) holds a submitted Metal command incomplete across the guarded lifecycle and verifies its later GPU result. It does not establish simultaneous GPU execution or general concurrency safety.

## Reproduction

Run CPU tests in the source repository:

```sh
xcrun clang++ -std=c++17 -Wall -Wextra -Werror -fsanitize=undefined \
 -Ibridge/experiments/video_context_lease -Ibridge/experiments/video_shared_guard \
 bridge/experiments/video_guarded_backend/GuardedAliasBackend.cpp \
 bridge/experiments/video_context_lease/VideoContextLease.cpp \
 bridge/experiments/video_guarded_backend/test.cpp -o /tmp/kepler-guarded-backend-test
/tmp/kepler-guarded-backend-test
```

Re-audit the exact retained GTX cohort without rerunning hardware work:

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
python3 bridge/experiments/video_guarded_backend_gpu/audit.py \
 --build "$R/video-guarded-backend-gpu-build-20261028-01" \
 --out "$R/video-guarded-backend-gpu-reaudit-new.json" --runs \
 "$R/video-guarded-backend-gpu-release-1-20261028" "$R/video-guarded-backend-gpu-observe-1-20261028" \
 "$R/video-guarded-backend-gpu-close-1-20261028" "$R/video-guarded-backend-gpu-negative-1-20261028" \
 "$R/video-guarded-backend-gpu-release-2-20261028" "$R/video-guarded-backend-gpu-negative-2-20261028" \
 "$R/video-guarded-backend-gpu-close-2-20261028"
```

The build-input SHA-256 is `4064037c9ead332eb2e65f39049e032fa86d72d3c650f05f384330861813d405`; the audit requires the exact frozen private lab and profile. Changed sources require a new qualification.
