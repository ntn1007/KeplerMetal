# Shared Metal client: bounded reference release

A process-local experiment on the GTX 880M found that a new `IOServiceOpen` of type 6 returned the same Mach port name and an IOKit-equal object as the connection held by a live Metal shared object. In two comparison processes, `IOServiceClose` on the additional open returned success, but creating another Metal command queue then failed. This observation narrows the [previous failure](VIDEO_SHARED_CLOSE_TIMING.md); it does not establish the kernel's internal ownership implementation.

In the observed profile, `mach_port_get_refs` reported send-right user references of 1 before the open, 2 afterwards and 1 after `IOConnectRelease`. These are local Mach user-reference counts, not kernel retain counts. Apple's SDK documents `IOConnectRelease` as releasing a reference, closing implicitly when the last reference is released. The experiment uses the [guard](../bridge/experiments/video_shared_guard/SharedAliasGuard.h) to require a successful extra open, equal port names, successful reflexive and cross-object IOKit comparisons, successful count queries and exactly one added reference before release. These are necessary observations for this experiment, not a general proof of safe ownership. The guard provides no synchronization; another thread or callback can change the state between checks and release. Callers must independently serialize the lifecycle and maintain object lifetimes.

## Results and limitations

The [seven-process audit](video-shared-guard-gpu-validation.json) checks the frozen build, signed process receipts, profile, controls, object identity and raw results. Two `release` processes each ran a native Metal compute shader on the GTX after the guarded release and produced 4,096 correct values against an independent CPU oracle: **8,192 verified values**. One `observe` control ran an additional 4,096 values, for **12,288 total**. Two no-dispatch controls retained 8,192 sentinel values; 160 boundary guard words were checked. Two `IOServiceClose` comparisons reproduced the queue-creation failure. Runs were serialized, and no hardware video execution was claimed.

The final cohort uses an ordinary Metal client with a process-local observer; it does not call the legacy AppleGVA provider or establish hardware decoding. This is a bounded experimental lifecycle correction, not an installed driver repair, a general solution for all aliases, or a performance measurement. The existing [VideoContextLease](VIDEO_CONTEXT_LEASE.md) still uses its original backend and is **not integrated or qualified with this guard**. Never infer that its teardown is safe for continued Metal use from this experiment.

A [subsequent witness](VIDEO_SHARED_LEASE_GPU.md) also exercises the actual type-3 association and the existing lease with a separate guarded backend.

## Re-audit and CPU tests

The archived GPU result is re-audited; these commands do not rerun the GPU cohort. They require the original private lab and matching frozen source/build profile:

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
EXP=bridge/experiments/video_shared_guard_gpu
python3 "$EXP/audit.py" --build "$R/video-shared-guard-gpu-build-20261028-01" \
  --out "$R/video-shared-guard-gpu-reaudit-new.json" --runs \
  "$R/video-shared-guard-gpu-observe-1-20261028" "$R/video-shared-guard-gpu-compare-1-20261028" \
  "$R/video-shared-guard-gpu-release-1-20261028" "$R/video-shared-guard-gpu-release-negative-1-20261028" \
  "$R/video-shared-guard-gpu-release-negative-2-20261028" "$R/video-shared-guard-gpu-release-2-20261028" \
  "$R/video-shared-guard-gpu-compare-2-20261028"
xcrun clang++ -std=c++17 -Wall -Wextra -Werror -fsanitize=undefined \
  bridge/experiments/video_shared_guard/test.cpp -o /tmp/kepler-shared-guard-test
/tmp/kepler-shared-guard-test
python3 -m unittest discover -s tests -p 'test_video_shared_guard_gpu.py' -v
```

The SDK `IOConnectRelease` declaration and documentation are in `IOKit/IOKitLib.h`; the experiment is tied to the exact recorded profile and build input SHA-256 `52762a5076d74a64b98d42f51d07feed86930e7878babb835f10936915307d5d`. No macOS, driver, firmware or OCLP component was modified.
