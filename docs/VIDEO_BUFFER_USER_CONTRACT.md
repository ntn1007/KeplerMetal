# Native user-mode path for video data buffers

The locally installed x86_64 dyld cache contains an `IOAccelerator` image with
UUID `198a776afe0335ee8e537b9f14caabaa`. Static analysis of ten named functions
now links the already observed type-3/type-6 association to the library's own
data-buffer request path. This analysis **does not call these private functions
or submit a selector**. The captured regions are matched against the current
cache, its image UUID, symbols, function boundaries and whole cache-part hash.
The direct branches and static import bindings are checked independently; a
static import is not a trace of the function reached at runtime.

In the analyzed image:

- `IOAccelVideoContextCreate` forwards to the general context constructor with
  type 3. The latter opens the connection, initializes an in-process context
  wrapper and calls the `IOConnectAddClient` import.
- `IOAccelSharedCreate` opens type 6 and requests a 16-byte reply using
  selector 9 on that **shared-client connection**. It also stores a pointer
  to the device wrapper; ownership is not yet qualified. This selector is not video-context selector 9.
- `IOAccelDeviceCreate` forwards to a device constructor that opens type 5.
  One of that constructor's queries uses selector 2 on the **device
  connection**, with a `0x258`-byte output capacity. Its returned data supplies
  a 32-bit field later stored in the device wrapper at offset `0x3c`.
- `IOAccelVideoContextRequestDataBuffer` forwards to
  `IOAccelContextRequestDataBuffer`. The latter rejects a first integer above
  15, copies the first two 32-bit input values into an 8-byte structure and
  calls the `IOConnectCallStructMethod` import with selector 3 on the context
  connection. The output capacity is **48 plus the device-wrapper field**
  described above. On its successful path it calls the resource-wrapper
  constructor and replaces the context's stored entry for that index.
- The user-mode context constructor initializes its slot count to 16, and the
  class-count getter reads that field. This is a wrapper capacity, **not proof
  that 16 classes are valid in the kernel**. The inherited kernel limit was
  previously found to be two only along a conditional static initialization
  path; its live value and the legal request values remain unverified.

The register interpretation follows the ordinary x86_64 calling convention;
Apple describes its [Intel ABI rules](https://developer.apple.com/documentation/xcode/writing-64-bit-intel-code-for-apple-platforms).
The named functions and their pointer relationships are private implementation
details, not a supported public API or a complete callable prototype. The
kernel's separate [method-table analysis](VIDEO_METHOD_CONTRACT.md) agrees on
selector 3 and an 8-byte input, but lengths alone do not establish input values,
resource lifetime, mapping ownership or synchronization. The earlier accepted
connection association does not construct all of these user-space wrappers.

The result is a concrete dependency chain for the next investigation: recover
the legitimate constructor contracts and resource lifetime using further
static evidence and observations of an ordinary client. Do not manufacture
wrapper pointers, guess sizes, or send an unqualified buffer request merely
because this sequence has been identified. No video decode or performance gain
is established.

## Reproduction

The capture tool saves vendor bytes locally under the ignored `bridge/results`
folder, never in the public repository. The following commands require the
exact cache and image UUID and **fresh output paths**. They create private
analysis artifacts, not loadable driver replacements. Use separate new output paths as shown.

```sh
CACHE=/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64
IMAGE=/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator
UUID=198a776afe0335ee8e537b9f14caabaa
python3 bridge/tools/capture_video_cache_symbols.py --cache "$CACHE" --image "$IMAGE" --expected-uuid "$UUID" --symbol _IOAccelVideoContextRequestDataBuffer --symbol _IOAccelContextRequestDataBuffer --symbol _IOAccelVideoContextGetDataBufferResource --symbol _IOAccelContextGetDataBufferResource --symbol _IOAccelResourceCreateDataBuffer --out bridge/results/new-buffer-capture
python3 bridge/tools/capture_video_cache_symbols.py --cache "$CACHE" --image "$IMAGE" --expected-uuid "$UUID" --symbol _IOAccelVideoContextCreate --symbol _IOAccelContextCreate --symbol _IOAccelDeviceCreate --symbol _IOAccelSharedCreate --symbol _IOAccelVideoContextGetDataBufferClassCount --symbol _IOAccelVideoContextRelease --symbol _IOAccelContextRelease --out bridge/results/new-lifecycle-capture
python3 bridge/tools/capture_video_cache_symbols.py --cache "$CACHE" --image "$IMAGE" --expected-uuid "$UUID" --symbol _IOAccelContextGetDataBufferClassCount --symbol _IOAccelVideoContextGetConnect --symbol _IOAccelDeviceCreateWithAPIProperty --out bridge/results/new-device-capture
python3 bridge/tools/video_buffer_user_contract.py --cache "$CACHE" --buffer bridge/results/new-buffer-capture --lifecycle bridge/results/new-lifecycle-capture --device bridge/results/new-device-capture --out /absolute/new-private-buffer-audit
python3 -m unittest discover -s tests -p test_video_buffer_user_contract.py -v
```

[Recorded static evidence and hashes](video-buffer-user-validation.json). A
separate copied-region mutation was rejected by the checker. No system driver,
OCLP, firmware or protected configuration was changed.
