# Observe a real Metal-owned IOAccelerator device object

An ordinary public-Metal client selects the GTX 880M by its NVIDIA PCI ancestry and creates a 4 KiB shared buffer. A separately linked, process-local observer forwards Metal's natural `IOAccelDeviceCreateWithAPIProperty` call and returns its result unchanged. On the pinned profile, the observer sees one non-null object associated with the selected `nvAccelerator`. While that object is still held by its creator and before returning it to the Metal caller, the observer verifies its `CFGetTypeID` against the type check in the pinned current `IOAccelDeviceGetConfig` implementation.

In two new signed processes, the observer then calls that exact pinned configuration function once with five real output pointers. It independently reads the five bounded object words before and after the call using `mach_vm_read_overwrite`. The call returns zero, and its five outputs match both object snapshots in each process:

```
768, 0, 0, 0, 1
```

These are **observed words, not identified meanings**. They are not decoded frames, a measurement of GPU performance or a guarantee that the legacy video provider accepts the object. The two control processes use the same signed executable and observer but do not call the configuration function. All four retain the ordinary Metal buffer's CPU byte check, finish with terminal nonoverlapping cooperative reservations, and use the same pinned source and binary. The offline auditor checks those receipts and rejects four intentional mutations of outputs, type evidence, control behavior and reservation state. [Machine-readable audit](device-object-validation.json).

The object is observed only during its original creation call; it is not retained, exported or passed to a historical provider. The observer checks the exact current config-function hash and its stored type identifier before the call, and refuses mismatches. The normal Metal call may perform its own driver activity; this test submits no explicit GPU kernel or private video selector. Wider object lifetimes, concurrent construction, semantics of the five values and video decoding remain unqualified. The reservation does not exclude WindowServer or unrelated processes.

This is a real device-object/configuration observation, beyond the previous [static analysis](IOACCEL_DEVICE_CONFIG.md) and [synthetic video probes](VIDEO_SYNTHETIC_SELECTOR.md). It does not modify a system driver, install a provider, or demonstrate hardware video.

## Reproduction

On the exact qualified host, use a fresh build and output paths, the common laboratory reservation root `LAB`, and the current matching `nvAccelerator` registry ID `RID`. The getter is called only in `config` mode. The runner validates system/profile hashes and signatures and the independent audit must pass; its counterfactual controls do not execute the GPU.

```sh
(
set -e
python3 bridge/experiments/device_object/experiment.py build --out "$LAB/results/device-object-build-new"
for item in observe:1 config:1 observe:2 config:2; do
  mode=${item%:*}; number=${item#*:}
  python3 bridge/experiments/device_object/experiment.py run \
    --build "$LAB/results/device-object-build-new" --out "$LAB/results/device-object-$mode-$number" \
    --lab "$LAB" --registry-id "$RID" --mode "$mode"
done
python3 bridge/experiments/device_object/audit.py --build "$LAB/results/device-object-build-new" \
  --runs "$LAB/results/device-object-observe-1" "$LAB/results/device-object-config-1" \
    "$LAB/results/device-object-observe-2" "$LAB/results/device-object-config-2" \
  --out "$LAB/results/device-object-audit-new.json"
)
```

The exact loaded IOAccelerator entry, installed driver files, kernel and kext UUIDs are profile-bound. A changed profile must be investigated and qualified before reuse; do not silently replace the pins. The retained raw observations and signed artifacts remain in the local lab; no vendor binaries are published.
