# Reusable video-context lifecycle

**Qualification warning:** A later [compute follow-up](VIDEO_CONTEXT_COMPUTE.md) found that creating a new Metal queue fails after this test association and teardown in the recorded scenarios. Successful close status is not sufficient to use this lease in an application that must continue using Metal.

`VideoContextLease` extracts the existing experimental type-3/type-6 lifecycle into a small reusable C++ component. A caller supplies an explicitly trusted backend and an already qualified, borrowed service handle. The component opens a video context, optionally opens and associates a shared client, and closes context before shared client. It records each status and attempts cleanup on failure. The component submits no GPU work or video selector and does not implement a decoder or Metal API.

The backend contract requires that any nonzero open output, including on failure, is an owned handle requiring closure. The native IOKit adapter deliberately does **not** treat a nonzero output from a failed `IOServiceOpen` as owned: it records `failure_output_unowned`, does not close the uncertain value, and the audit rejects the run. No such outcome occurred in this cohort. Equal context/shared port names are treated as ambiguous: association is refused and the value is closed once. A close error is preserved and not retried because the connection state is uncertain. The caller must keep backend state and any required Metal device alive, serialize access, use nonthrowing callbacks and handle close failures. The lease is neither thread-safe nor a general proof of kernel ownership.

## Validation

A pinned test gate uses the component on the actual service selected by controlled AppleGVA 10.13.6. Two signed, nonoverlapping processes each open type 3 and type 6, associate them and close both successfully; a context-only control succeeds and a wrong-name control makes no gate call. A Metal device with the same registry ID remains alive through teardown. The [six-process audit](video-provider-lease-validation.json) checks frozen sources and build, signed receipts, route/identity controls, return codes, declared imports and six CPU reference images (2,764,800 bytes). Four hardware-required cases still return `-12913` and zero images. The test gate returns 14 and does not call the Sierra provider. AppleGVA selection and previous policy/dependency substitutions remain process-local.

A pure C++ mock test covers successful association, context-only operation, open failures, null and duplicate handles, association failure, failed close, destructor cleanup, repeat close and invalid input. Its normal build and UndefinedBehaviorSanitizer run passed on the iMac. AddressSanitizer terminated with signal `SIGILL` on the iMac, and an independently compiled empty ASan control did the same; the reason is undetermined. The exact three test source hashes were checked after SSH transfer to the MacBook M1 Max, where an arm64 build with AddressSanitizer and UndefinedBehaviorSanitizer passed. This is a portable CPU test, **not** a Kepler GPU test. Fourteen portable Python provider-auditor tests also passed.

The lease does not establish selector compatibility, correct resource or buffer lifetime, actual video decoding, hardware-engine execution, performance, or application-transparent integration. The shared client is newly opened for the test; it is not identified as Metal's own internal shared client. The cooperative GPU reservation does not exclude WindowServer, and framework/driver-internal calls are not exhaustively traced. No macOS, driver, firmware or OCLP component was changed.

## Reproduction

The mock is self-contained and CPU-only:

```sh
EXP=bridge/experiments/video_context_lease
xcrun clang++ -std=c++17 -Wall -Wextra -Werror "$EXP/VideoContextLease.cpp" "$EXP/test.cpp" -o /tmp/kepler-video-lease-test
/tmp/kepler-video-lease-test
python3 -m unittest discover -s tests -p 'test_video_provider_*.py' -v
```

The recorded GPU-profile cohort requires the exact private lab and boot-specific ID and is **re-audited**, not rerun, by:

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
EXP=bridge/experiments/video_provider_lease
python3 "$EXP/audit.py" --build "$R/video-provider-lease-build-20261028-01" \
  --out "$R/video-provider-lease-reaudit-new.json" \
  --hosts "$R/video-provider-lease-inspect-20261028-01" "$R/video-provider-lease-attach-20261028-01" \
  "$R/video-provider-lease-context-20261028-01" "$R/video-provider-lease-wrong-20261028-01" \
  "$R/video-provider-lease-attach-20261028-02" "$R/video-provider-lease-cpu-20261028-01"
```

The auditor pins the build hash, source and current-profile evidence; a new build or changed profile requires requalification. Vendor binaries and frame captures stay in the private lab.
