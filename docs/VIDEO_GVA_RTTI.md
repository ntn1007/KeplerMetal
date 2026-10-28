# AppleGVA selector-2 constructor: static type metadata

The previously observed selector value `2` points, in the pinned static code,
to an allocation path followed by a constructor relay at image offset 233054.
The relay jumps to offset 232918, which calls a base initializer at 117024 and
then contains a store of a vtable address point into the object. The previous
[process-local observer](VIDEO_GVA_REGISTER.md) recorded the allocator call in
three counterfactual H.264 requests, not a completed constructor.

The locally mapped AppleGVA cache identifies the static type metadata at that
address point as `Flow_QT0`, with single base `Flow`. The audit verifies the
cache pointer chains, type names, and the corresponding libc++abi type-info
vtable symbols. A separately compiled original CPU-only C++ program checks the
type-info layout on this host. See the [Itanium C++ ABI RTTI description](https://itanium-cxx-abi.github.io/cxx-abi/abi.html#rtti).

This is **not a live readback of an AppleGVA object**. The previous execution
recorded a selector and a stack inside the base initializer; it did not show
that the initializer returned or that the vtable store executed. The captured
constructor bytes were inspected on disk, not verified as live code in those
earlier runs. The type names do not establish a codec, hardware provider, or
cause of failure. The first ten static pointer slots resolve to function starts;
the full vtable extent, signatures and actual runtime dispatch remain unknown.
The test used process-local property and board-policy substitutions; hardware
decode still returned -12913 and zero images.

## Base-constructor branch and historical stack

In a separately recorded earlier process, the board observer captured a stack
return at image offset 117072. In the pinned on-disk base-constructor region,
the preceding direct call targets 148746; the earlier stack mapper also places
the next frame in that target. The static code leading to the call compares a
32-bit word with `0xffffffff` and branches around the call when equal. Thus,
**if the pinned code and normal entry flow apply to that stack**, reaching the
call is consistent with the compared word being different from `0xffffffff`.
The word and comparison were not recorded, and another entry path or code
drift cannot be excluded from the historical stack alone. The meaning of the
word, the callee's return, and constructor completion remain unknown. This
historical stack and the selector-2 measurement are from separate runs.

REA/Ghidra evidence `ev_f9bb0e6b5698dd40ae995e90c2aeeab583e9a5efba8a8cb6b11e57cc00292bfe`
covers the 157-byte recovered body of the captured 176-byte region. The
[separate correlation receipt](video-gva-base-branch-validation.json) binds
the region, analysis container and retained historical stack-map receipt; it
does not re-run the historical process or verify every live frame.

```bash
R='/path/to/nvidia-880m-lab/bridge/results'
python3 bridge/experiments/video_gva_rtti/base_branch_audit.py \
  --capture "$R/gva-flow-base-20261029-01" \
  --rea "$R/gva-flow-base-rea-20261029-01.private.json" \
  --stack-map "$R/gva-overlay-stack-map-reaudit-20261028-01.json" \
  --out "$R/gva-flow-base-branch-audit-new.json"
```

## Evidence and reproduction

The audit checks AppleGVA image UUID `ca5414f369373c059ea2d82b35afd4f0`.
The [sanitized audit receipt](video-gva-rtti-validation.json) records code and
analysis-container hashes, REA evidence IDs, the historical selector receipt,
and CPU calibration. The original vendor bytes,
analysis containers and private REA bundles stay in the local lab. The audit
executes no vendor code, Metal workload or GPU work, and modifies no system file.

On the exact qualified profile, with the previously captured private inputs:

```bash
R='/path/to/nvidia-880m-lab/bridge/results'
python3 bridge/experiments/video_gva_rtti/audit.py \
  --cache /System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64 \
  --thunk "$R/gva-selector2-constructor-20261029-01" \
  --init "$R/gva-selector2-init-20261029-01" \
  --thunk-rea "$R/gva-selector2-thunk-rea-20261029-01.private.json" \
  --init-rea "$R/gva-selector2-init-rea-20261029-01.private.json" \
  --witness-audit "$R/gva-register-audit-20261029-02.json" \
  --out "$R/gva-selector2-rtti-audit-new.json"
python3 -m unittest discover -s tests -p 'test_video_gva*.py'
```

The audit requires exact pinned inputs and a fresh output path. It will refuse
profile drift; this command does not recreate the historical GPU observation.
