# Historical NVIDIA provider registration: static input bounds

A focused offline follow-up, later found to duplicate part of an earlier private-lab analysis, examines the separately acquired 10.12.6 `GeForceVADriver` x86_64 slice, SHA-256 `bf2110a8a74786fe06da672e35f05a0dbd554aa651a83bacf02753c5899ef567`. This is **not** the currently installed stub, and it has not been qualified for the current kernel or GPU video execution. The earlier [dispatch comparison](VIDEO_PROVIDER_DISPATCH.md) documents a material difference in the historical and current selector paths.

The historical factory at `0x1f3dc` passes its second argument to a registration function at `0x2afa0`. The pinned registration instructions examine a 32-bit mask at input offset `0x10`; a zero mask does not follow the successful registration path. They find the highest set bit among the 32 positions and copy that many 32-bit elements **plus one** from the array addressed by the pointer at input offset `0x08`. Thus a sparse mask such as `0x80000001` still results in copying 32 elements, not two. Whether the caller supplied valid mapped memory and the meanings and ownership of these words are not established by this static observation.

The factory also passes the input's first 32-bit word to a selection function at `0x2ba56`. For an existing registration, the pinned selection instructions check the corresponding mask bit, check that the index is below the stored count, and require its copied entry to be nonzero. Only after these conditions does that function store the value and index in the object. The checks are necessary on this code path; satisfying them does **not** prove factory success, a legitimate AppleGVA input, selector compatibility, buffer validity or GPU decoding. The names and semantics of the input values remain unknown. In particular, this analysis does not equate the mask to the modern `IOGVACodec` property.

Ghidra 12.1.4 evidence `ev_122fc54c910d30b1fd59c051b77166f63d26bb2410be662865dcb02643d522bc` and `ev_740fd0cfab7948a61300a27da572e9cda25cb1b28442af931601b1b8e92a422d` cover the full 255-byte registration and 115-byte selection function bodies. The factory body is 571 bytes. The [local verifier](../bridge/experiments/video_provider_registration/inspect.py) checks the entire binary and those three regions against fixed hashes and exercises an independent conservative model of the observed necessary conditions. Its [report](video-provider-registration-validation.json) contains no proprietary instructions. The full REA snapshot remains in the private lab. Decompiler pseudocode is not source code; inspect the pinned instructions and reference edges before extending this interpretation.

Four offline tests cover all 32 single-bit masks, sparse masks, disabled indices, zero entries, short arrays, invalid types and input identity refusal. The model rejects short arrays before selection even where a selected index is low: this is deliberate, because the historical registration copies through the highest bit. The model never builds a provider argument, loads a binary, submits selectors or accesses a GPU.

The [prior synthetic sequence](VIDEO_SYNTHETIC_SEQUENCE.md) used index 0, mask 1 and a one-element array containing 1. Those values satisfy the local checks above but were fabricated; they do not establish a real producer or video transport. The [subsequent re-audit](VIDEO_PROVIDER_FIELDS.md) recovers prior observations of a historical AppleGVA caller and clarifies what remains unknown about these fields. No framework, driver, OCLP or firmware was modified; no new runtime or performance result is claimed.

## Reproduction

Use the privately obtained exact x86_64 slice from the earlier audit; see [dependencies](DEPENDENCIES.md). The tool rejects a changed slice and creates a fresh report.

```sh
python3 bridge/experiments/video_provider_registration/inspect.py \
  --provider "$LAB/results/video-sierra-provider-20261027-01/GeForceVADriver-10.12.6-x86_64.private" \
  --out "$LAB/results/video-provider-registration-new.json"
python3 -m unittest discover -s tests -p test_video_provider_registration.py -v
```
