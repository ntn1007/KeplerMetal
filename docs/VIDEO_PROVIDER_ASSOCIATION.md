# Association on the legacy AppleGVA selected service

The [preceding context test](VIDEO_PROVIDER_CONTEXT.md) opened a type-3 video context on the actual GTX service selected by a controlled legacy AppleGVA caller. This follow-up keeps a Metal device on the same registry ID alive, opens a type-3 context and a **new** type-6 shared connection on that selected service, and invokes the public `IOConnectAddClient(context, shared)` once. The probe closes the context and then the shared connection before releasing its Metal device. It does not acquire or identify Metal's own internal shared client.

Two signed, nonoverlapping hardware-required processes each report status zero for both opens, the association and both closes; the returned port names were distinct. A context-only comparison opens and closes the type-3 connection without creating or associating a shared client. A wrong-name control never reaches the gate. Inspection and CPU controls complete the six-process cohort. Six software frames match **2,764,800 bytes** of their pinned reference; all four hardware-required requests still return `-12913` with zero frames.

AppleGVA 10.13.6 is explicitly selected in this process and previous process-local policy/dependency substitutions remain. A test gate replaces the installed NVIDIA create-stub lookup and returns 14; the historical Sierra provider is **not** invoked. Before any open, the gate checks the caller identity and selected service's send right, class and registry ID, and verifies that the retained default Metal device has the same ID. The borrowed AppleGVA service right is neither retained nor released. The gate uses public IOKit open/close and `IOConnectAddClient` calls, sends no explicit GPU work or private video selector, and its import table excludes `IOConnectCall*`. Framework initialization and driver-internal work are not exhaustively traced.

The zero association status shows acceptance of this request in the recorded scenarios, not complete object lifetime, video-engine execution, correct resource handling, Sierra compatibility or transparent integration into applications. The connection belongs to the test gate and is closed before returning; it is not supplied to the historical provider. The cooperative reservation cannot exclude WindowServer. No system driver, framework, OCLP or firmware was modified.

The [cohort audit](video-provider-association-validation.json) rechecks the pinned source/build, signed executables, actual input assets, terminal nonoverlapping receipts, identity and route controls, output data and required imports. Twelve portable provider unit tests pass, including rejection of a modified association status. Two exploratory builds failed to compile and remain in the lab; no hardware process came from them and they are excluded from the cohort.

## Re-audit the retained exact build

This historical build requires the private lab, pinned AppleGVA fixture and driver profile, and the boot-specific accelerator ID. The coordinator expects `$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge`. The auditor pins the recorded build rather than silently accepting a new compilation; requalify after a reboot or profile change. No vendor binaries or decoded frames are distributed.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
EXP=bridge/experiments/video_provider_association
python3 "$EXP/audit.py" --build "$R/video-provider-association-build-20261028-03" \
  --out "$R/video-provider-association-reaudit-new.json" \
  --hosts "$R/video-provider-association-inspect-20261028-01" \
  "$R/video-provider-association-pair-20261028-01" "$R/video-provider-association-attach-20261028-01" \
  "$R/video-provider-association-wrong-20261028-01" "$R/video-provider-association-attach-20261028-02" \
  "$R/video-provider-association-cpu-20261028-01"
python3 -m unittest discover -s tests -p 'test_video_provider_*.py' -v
```

The live video selector and buffer contract remains the next substantive barrier; this association does not authorize sending an unqualified selector to the display GPU.
