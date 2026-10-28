# Video context opened from the selected legacy service

The [previous experiment](VIDEO_PROVIDER_SERVICE.md) identified the actual service selected by a controlled legacy AppleGVA caller as the GTX `nvAccelerator`. In this follow-up, the same process-local gate optionally attempts a public `IOServiceOpen` of **type 3** on that selected service and immediately closes the returned connection. It first checks the pinned caller, selected send right, service class and this boot's registry ID `4294968416`. The borrowed service right is neither retained nor released by the gate.

Two signed, nonoverlapping hardware-required processes each record **one successful open and one successful close**, both status zero. A same-gate comparison with the probe disabled records no open or close; a wrong-name control does not reach the gate. An inspection and a software decode control complete the six-process cohort. The software images match 2,764,800 reference bytes. All four hardware-required tests, including the disabled-probe and wrong-name controls, still return `-12913` and zero images.

This extends the earlier [separate type-3 test](VIDEO_CONTEXT_CURRENT.md) by opening the actual service supplied by the legacy caller in the same process. It is still a test gate: AppleGVA 10.13.6 is selected explicitly, prior process-local policy/dependency substitutions remain, and the NVIDIA Sierra provider is **not called**. The test gate makes no `IOConnectCall*` request and no explicit GPU dispatch; its import list is audited separately. Initializers and activity internal to public IOKit open/close are not exhaustively traced. The returned connection is closed before the gate returns; retaining it or passing it into any provider has not been qualified. This does not prove compatibility of the legacy provider, live selector dispatch, a video submission or decoding.

The [audit](video-provider-context-validation.json) validates the frozen source and build, signed executables, assets, calibration, six terminal nonoverlapping receipts, route controls, status codes and CPU frame bytes. The GPU reservation is cooperative and does not exclude WindowServer. Ten portable unit tests across provider registration, fields, identity and context auditors pass. The calibration confirms that a known GTX service passes the local identity policy while a null service and disabled probe do not.

The first exploratory build failed compilation because a declaration preceded its type. A second build completed a six-process exploratory cohort but labeled its zero GPU dispatches as zero GPU calls, which could be misunderstood because it did open the context. Both are preserved locally and excluded from the final counts. The final build uses the explicit `gpu_dispatches` label and a new six-process cohort.

## Re-audit the exact retained build

The exact prior local build, pinned driver/kext profile, AppleGVA image, fixture and boot-specific ID are required. The coordinator expects `$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge`; the audit pins the build hash and does not silently accept a rebuild. A reboot, changed driver or new build requires independent requalification. No proprietary binaries or images are distributed.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
EXP=bridge/experiments/video_provider_context
python3 "$EXP/audit.py" --build "$R/video-provider-context-build-20261028-03" \
  --out "$R/video-provider-context-reaudit-new.json" \
  --hosts "$R/video-provider-context-final-inspect-20261028" \
  "$R/video-provider-context-final-probe-1-20261028" "$R/video-provider-context-final-off-20261028" \
  "$R/video-provider-context-final-probe-2-20261028" "$R/video-provider-context-final-wrong-20261028" \
  "$R/video-provider-context-final-cpu-20261028"
python3 -m unittest discover -s tests -p 'test_video_provider_*.py' -v
```

The next barrier is the live selector and buffer contract. This successful open does not justify sending the historical provider's unqualified selectors to the current kernel. The experiment does not modify macOS, OCLP, firmware or installed drivers.
