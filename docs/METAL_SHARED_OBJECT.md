# Observe Metal's device-to-shared object link

An ordinary Metal client selects the GTX 880M by PCI ancestry and creates a 4 KiB shared buffer. A separately linked, process-local observer forwards the naturally occurring `IOAccelDeviceCreateWithAPIProperty` and `IOAccelSharedCreate` calls, then returns both original objects unchanged. No object is manufactured or passed to the legacy video provider.

In four independent signed processes, the matching device constructor returns one non-null object. The shared constructor receives that same pointer and returns one non-null object; its observed CoreFoundation type matches the pinned `IOAccelSharedGetTypeID` storage. A bounded read of the shared object's `0x10` field matches the device pointer supplied to the constructor. The currently loaded constructor and type-getter code are hash-pinned before interpreting that field. Addresses themselves are not recorded in the report.

Two processes also repeat the [device configuration read](METAL_DEVICE_OBJECT.md), obtaining the same five words; two controls do not call that getter. The four processes use the same signed executable, preserve the ordinary Metal buffer's CPU-byte check, and end with terminal, nonoverlapping cooperative reservations. The offline auditor rejects five mutated results or receipts, including a changed shared/device link. [Machine-readable audit](shared-object-validation.json).

This observes pointer equality during the two natural creation calls. It **does not prove a retain operation, subsequent lifetime, context association, real video-resource compatibility or decoding**. The observer neither releases nor exports the objects and makes no explicit video-selector call or GPU dispatch. Ordinary Metal may perform internal driver activity; the observation does not trace it exhaustively. The common reservation does not exclude WindowServer or unrelated processes.

This gives a real, process-local device/shared relationship to compare with the [historical video provider's requirements](VIDEO_BUFFER_USER_CONTRACT.md). It is not yet a bridge to that provider, a replacement driver, or evidence of a performance gain.

## Reproduction

Use a new build, a common lab root `LAB` and the current qualified `nvAccelerator` registry ID `RID`. The exact system and IOAccelerator function hashes are checked; changed profiles must be qualified separately. Only `config` mode calls the pinned configuration getter.

```sh
(
set -e
python3 bridge/experiments/shared_object/experiment.py build --out "$LAB/results/shared-object-build-new"
for item in observe:1 config:1 observe:2 config:2; do
  mode=${item%:*}; number=${item#*:}
  python3 bridge/experiments/shared_object/experiment.py run \
    --build "$LAB/results/shared-object-build-new" --out "$LAB/results/shared-object-$mode-$number" \
    --lab "$LAB" --registry-id "$RID" --mode "$mode"
done
python3 bridge/experiments/shared_object/audit.py --build "$LAB/results/shared-object-build-new" \
  --runs "$LAB/results/shared-object-observe-1" "$LAB/results/shared-object-config-1" \
    "$LAB/results/shared-object-observe-2" "$LAB/results/shared-object-config-2" \
  --out "$LAB/results/shared-object-audit-new.json"
)
```

The host and observer sources are published; the signed artifacts and vendor bytes used in checking remain local. No system driver or OCLP component is modified.
