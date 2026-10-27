# Native video buffer wrapper lifetime

The pinned `IOAccelerator` cache image registers four CoreFoundation classes:
`IOAccelDevice`, `IOAccelShared`, `IOAccelContext` and `IOAccelResource`.
Each registration reaches a class record with version zero and a callback at
byte offset `0x20`. That offset matches the `finalize` field of Apple's
[published CFRuntimeClass definition](https://github.com/apple-oss-distributions/CF/blob/dc54c6bb1c1e5e0b9486c1d26dd5bef110b20bf3/CFRuntime.h).
This older public definition is a **layout comparison**, not proof that the
installed CoreFoundation implementation is identical. The class names,
registration calls, cache rebase chains, callback addresses and function bytes
are all checked against the pinned cache; no callback was observed executing.

The callback candidates show the following static paths:

- The context candidate visits 16 resource slots, calls the `CFRelease` import
  for non-null entries, clears them and then calls `IOConnectRelease` on its
  connection. This supports the previously observed 16-slot wrapper capacity,
  without establishing 16 valid kernel buffer classes.
- The resource allocator calls `CFRetain` on its shared-wrapper argument and
  stores that pointer. The resource callback later calls `CFRelease` on that
  stored shared wrapper. Before that release, a conditional path decrements a
  counter; when it reaches zero, the callback calls `IOConnectCallMethod` with
  selector 1 on a connection reached through the shared wrapper. This is a
  **shared-client selector**, not context selector 1. Its input semantics and
  runtime effect is not yet qualified. A later [dispatch analysis](VIDEO_SHARED_DELETE.md)
  identifies the statically selected kernel path and its limits.
- The shared and device callback candidates each call `IOConnectRelease` on
  their connection. The shared callback also walks local bookkeeping after
  releasing the connection reference. Static inspection does not prove the
  lifetime of every dependent object, successful cleanup, or every failure path.
- The context resource getter reads a pointer from a stored slot and returns
  it without a direct retain call in the inspected function. That observation
  is not a complete ownership contract for callers, nor does it prove that the
  memory is accessible or safe to write.

Apple documents [`IOConnectRelease`](https://developer.apple.com/documentation/iokit/1514511-ioconnectrelease)
as releasing a connection reference, with an implicit close when the last
reference goes away. This differs from the explicit `IOServiceClose` used by
our earlier [raw-connection witness](VIDEO_CONTEXT_ASSOCIATION.md). That
witness established accepted association and return statuses; it did **not**
exercise or validate this native CF-wrapper release path.

These findings change the next experiment: releasing a resource wrapper may
itself invoke an additional selector, so a safe test must first qualify that
shared-client operation and observe a real producer/consumer lifetime. Do not
invent wrapper pointers, assume a borrowed pointer is retained, or treat a
successful context close as proof of complete native resource cleanup. No
resource request, hardware video command or decode was performed in this static
analysis.

## Reproduction

The cache captures and analysis objects remain private under ignored
`bridge/results`; the [published record](video-buffer-lifetime-validation.json)
contains only identifiers, hashes and bounded findings. Reproduction requires
the exact pinned cache and fresh output paths. `capture_video_cache_symbols.py`
and `inspect_video_cache.py` enforce their output location beneath
`bridge/results`.

```sh
CACHE=/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64
IMAGE=/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator
UUID=198a776afe0335ee8e537b9f14caabaa
python3 bridge/tools/capture_video_cache_symbols.py --cache "$CACHE" --image "$IMAGE" --expected-uuid "$UUID" --symbol ___IOAccelDeviceGetTypeID_block_invoke --symbol ___IOAccelSharedGetTypeID_block_invoke --symbol ___IOAccelContextGetTypeID_block_invoke --symbol ___IOAccelResourceGetTypeID_block_invoke --symbol _IOAccelResourceGetDataBytes --symbol _IOAccelResourceGetClientShared --symbol _IOAccelResourceRelease --symbol _IOAccelSharedRelease --out bridge/results/new-class-registration
python3 bridge/tools/capture_video_cache_symbols.py --cache "$CACHE" --image "$IMAGE" --expected-uuid "$UUID" --symbol __IOAccelResourceAlloc --symbol _IOAccelDeviceRelease --symbol _IOAccelVideoContextRelease --symbol _IOAccelVideoContextGetDataBufferResource --out bridge/results/new-resource-retain
python3 bridge/tools/inspect_video_cache.py --cache "$CACHE" --image "$IMAGE" --expected-uuid "$UUID" --offset 0x3d9a --capture-region --out bridge/results/new-finalizer-device
python3 bridge/tools/inspect_video_cache.py --cache "$CACHE" --image "$IMAGE" --expected-uuid "$UUID" --offset 0x376c --capture-region --out bridge/results/new-finalizer-shared
python3 bridge/tools/inspect_video_cache.py --cache "$CACHE" --image "$IMAGE" --expected-uuid "$UUID" --offset 0x3906 --capture-region --out bridge/results/new-finalizer-context
python3 bridge/tools/inspect_video_cache.py --cache "$CACHE" --image "$IMAGE" --expected-uuid "$UUID" --offset 0x26a5 --capture-region --out bridge/results/new-finalizer-resource
python3 bridge/tools/video_buffer_lifetime.py --cache "$CACHE" --registration bridge/results/new-class-registration --resource-alloc bridge/results/new-resource-retain --getters bridge/results/new-buffer-capture --device bridge/results/new-finalizer-device --shared bridge/results/new-finalizer-shared --context bridge/results/new-finalizer-context --resource bridge/results/new-finalizer-resource --out /absolute/new-private-lifetime-audit
python3 -m unittest discover -s tests -p test_video_buffer_lifetime.py -v
```

`new-buffer-capture` is produced by the [prior buffer-path reproduction](VIDEO_BUFFER_USER_CONTRACT.md).
A copied finalizer region with one modified byte was rejected. No driver,
OCLP, firmware or protected configuration was changed.
