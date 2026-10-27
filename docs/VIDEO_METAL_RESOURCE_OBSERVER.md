# Native Metal resource observation

This is a bounded, process-local diagnostic on the existing GTX 880M stack, not a driver replacement or a video decoder. Its purpose is to observe ordinary public Metal allocation through IOAccelerator before considering any resource-management experiment. It does not submit GPU commands or call a private selector on a device. The two deliberate selector calls in the control use a null Mach port and cannot reach the driver.

## Observation on the pinned iMac profile

On 27 October 2026, an unprivileged signed host opened the selected `nvAccelerator` for its calibration and closed it successfully. A separately linked, signed observer captured four expected control events: the null-port method and struct-method failures and the type-3 open and close. An earlier observer embedded in the executable recorded none of these calls despite successful open/close; its oracle failed as intended. This is why the calibration is mandatory and why an empty trace alone is not evidence of absence.

Two subsequent, sequential fresh processes selected the Metal device on the same NVIDIA PCI ancestor, created one 4,096-byte shared `MTLBuffer`, and checked a CPU-written pattern. Each captured 28 metadata-only events. Each observed one type-6 shared-client open and **11 successful selector-0 calls** from `IOAccelResourceCreate`, during the phase encompassing buffer creation and the CPU check. Neither trace observed a selector-1 method call in the recorded window. These 11 calls may include internal allocations; the trace does **not** associate any one call with the public buffer. The buffer's bytes were tested by the CPU, not a GPU kernel.

Recorded phases denote **call completion**, not necessarily entry. The observer cannot promise coverage of calls through every image or asynchronous work. No observed selector 1 does not establish that deletion failed to occur: deferred cleanup, caching, unobserved paths and teardown after capture are possible. No resource ID, scalar value or payload content is recorded. The trace cannot establish hardware video decoding, GPU execution, a performance gain, or the behavior of unrelated Metal programs. A previous static selector-1 analysis is a separate result, not validated here by invoking it.

The public [validation summary](video-metal-resource-observer-validation.json) contains hashes of retained local evidence; the full host outputs and binaries remain in the lab. The summary can be checked against those retained files with the audit tool. Installed system components remain untouched; observer interposition affects only the test process. The program checks the exact pinned system-file hashes, loaded kext UUIDs, kernel UUID, unprivileged UID and NVIDIA PCI IDs before testing. This is a machine-specific profile, not a portability claim.

## Reproduction on the qualified machine

Run from the repository root, with a pre-existing lab `results` directory and a cooperative reservation root shared with other tests. Use fresh result names for every run. The build output's absolute path is embedded in the signed observer library, so keep the build directory in place for the duration. The script refuses changed profiles and frozen sources; review and qualify a new profile rather than disabling these checks.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
python3 bridge/tools/video_metal_resource_observer.py build --out "$LAB/results/resource-build-new"
python3 bridge/tools/video_metal_resource_observer.py run --build "$LAB/results/resource-build-new" --out "$LAB/results/resource-inventory-new" --reservation-root "$LAB" --mode inventory
```

Read `gpu_registry_id` from the verified inventory and set `RID` to that value, not a stale identifier. Before any buffer test, run the observer control and require `HOOK_CONTROLS_PASS`:

```sh
RID='<registry ID printed by inventory>'
python3 bridge/tools/video_metal_resource_observer.py run --build "$LAB/results/resource-build-new" --out "$LAB/results/resource-control-new" --reservation-root "$LAB" --mode control --registry-id "$RID"
python3 bridge/tools/video_metal_resource_observer.py run --build "$LAB/results/resource-build-new" --out "$LAB/results/resource-buffer-a-new" --reservation-root "$LAB" --mode buffer --registry-id "$RID"
python3 bridge/tools/video_metal_resource_observer.py run --build "$LAB/results/resource-build-new" --out "$LAB/results/resource-buffer-b-new" --reservation-root "$LAB" --mode buffer --registry-id "$RID"
python3 bridge/tools/audit_video_metal_resource_observer.py "$LAB/results/resource-control-new" "$LAB/results/resource-buffer-a-new" "$LAB/results/resource-buffer-b-new"
```

`wrong-target` is a separate negative control: it must return `CONTROL_PASS` without opening a device. Its result is not part of the three-process audit. The audit rechecks recorded inputs, signatures, the exact target and completion order and rejects missing controls or missing observed creates. It doesn't replace the live tests or prove full trace coverage. GPU reservation coordinates participating lab runners; it does not provide exclusive system-wide access to the display GPU.
