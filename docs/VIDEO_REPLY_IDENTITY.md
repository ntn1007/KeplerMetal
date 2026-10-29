# Video reply fields and shared resource identity

On the pinned **on-disk** IOAcceleratorFamily2 image, the inherited video `getDataBuffer` path writes a 32-bit resource field from `resource+0x38`, offset `0x100`, into the 48-byte reply at offset `0x28`. It passes the same resource to `IOAccelResource2::getClientSharedAddresses`, supplying the reply locations at `0x18` and `0x20` as output pointers. The accessor forwards that same 32-bit field to `IOAccelSharedNamespace2::getClientSharedAddressesForId`.

The ordinary shared-client `new_resource` path calls the **same accessor**, supplying output pointers at offsets `0x10` and `0x18` of its different reply structure. This is a static relationship between two construction paths; it does not establish that video and ordinary resources have interchangeable replies or shared lifetimes.

The namespace routine invokes the shared-machine address helper twice, using namespace subobjects at `+0x50` and `+0x90`. The pinned helper divides the resource ID by a per-machine value, checks the resulting index against a bound and checks the selected mapping field for nonzero. On the successful path it computes an address from the selected mapping and a stride. On an out-of-range or zero-mapping branch it calls `_panic`; division occurs before that branch. **Neither that branch nor a zero divisor was observed at runtime.** The analysis does not establish that a selector caller controls the ID or can reach these conditions. Do not manufacture a reply, ID or pointer from this finding.

Other fields at video reply offsets `0x00`, `0x08` and, conditionally, `0x10` are written via distinct paths. Their exact types, live values and ownership are not established here. The names of the two accessor outputs do not prove GPU virtual addresses, CPU accessibility, synchronization or usable length. The returned status and layout remain unqualified on the current driver.

## Evidence and limits

A prior complete Ghidra dossier for `getDataBuffer` is linked to four new REA/Ghidra 12.1.4 dossiers for the resource accessor, namespace helper, shared-machine helper and ordinary resource path. [The source-only audit](../bridge/tools/video_reply_identity.py) checks the full installed image hash, five function-body hashes, evidence identities and selected instruction anchors. [Sanitized receipt](video-reply-identity-validation.json). Six CPU mutation tests challenge the evidence checks; four existing reply-bounds tests also pass.

Evidence IDs are `ev_73185ac90e6c691e4d2eca5f95e61e33d6f341b329cd17b6934db77cab79f6b9`, `ev_96202f162ea88502ff6568d8488de45dd586c1f9d38099f911bea7570ecc9932`, `ev_48229cf29413a8fc19babaea90fc6c7b1492cf8a5d20abe9313aec4e01c24e52`, `ev_1e269c37f956818dbb4b05eeb92074a4d0bd6b1fdb3078e35e66db4772268227`, and `ev_a0789b08c009780d402edf2bfb453ee445063f7da7e6243e98e6b475a03a2c29`. Vendor instructions, analysis bundle and binary remain private.

No native video method, selector or GPU command was issued. File identity does not prove live kernel bytes or runtime vtable dispatch. No live reply, real video resource, complete cleanup, hardware decode, driver repair or performance gain is established. The [existing guard](VIDEO_BUFFER_REQUEST_GUARD.md) must continue to refuse an unqualified request; a legitimate producer and runtime ownership evidence are still required.

## Reproduction

The pinned private REA bundle and previous private dossier remain in the local lab. Use a fresh output path; a different profile requires new analysis and qualification.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
python3 bridge/tools/video_reply_identity.py \
 --driver /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2 \
 --prior "$LAB/results/video-method-contract-20261027/getDataBuffer.private.json" \
 --rea "$LAB/results/video-reply-fields-rea-20261029-01.private.json" \
 --out "$LAB/results/video-reply-identity-new.json"
python3 -m unittest discover -s tests -p 'test_video_reply_identity.py' -v
python3 -m unittest discover -s tests -p 'test_video_reply_bounds.py' -v
```
