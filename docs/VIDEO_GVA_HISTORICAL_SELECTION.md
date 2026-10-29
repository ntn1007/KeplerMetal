# Historical NVIDIA candidate: counting is not selection

This offline follow-up examines the same pinned 10.13.6 AppleGVA function and
retained Ghidra evidence used by the [historical classification comparison](VIDEO_GVA_HISTORICAL_CLASSIFICATION.md).
It does not run AppleGVA or alter any Apple or NVIDIA component.

For a node passing the preceding flag checks, value `0x01040008` increments a
candidate count and places that node in `R15`. The function later checks that
count. On the **single-counted-candidate** path, if the NVIDIA-class register
is nonzero, request values `5` and `9` branch to the function's return before
the later output append. Other policy checks can also return early. The exact
meanings of these request values have not been established. The function has
other paths and this observation does not establish its behavior for all input
lists or request values.

This refines the earlier evidence: the old NVIDIA-labelled branch counted a
candidate, but a count is not itself an output-list entry or proof of a usable
decoder. The [legacy runtime witness](VIDEO_LEGACY_BACKEND.md) separately found
an installed NVIDIA creation entry returning 14 on its scoped historical path.
These are different observations; neither proves why the current AppleGVA
request produces an empty list or establishes which hardware engine executes.
The next useful observation is to bind the current request and output-list
consumption to real values and provider calls, rather than merely forcing the
historical count.

## Evidence and reproduction

The [auditor](../bridge/experiments/video_gva_historical_selection/audit.py)
checks the historical image SHA-256, Mach-O identity, complete function-body
hash, archived REA bundle hash and exact evidence identity, and selected
control-flow instructions. It creates a fresh receipt. The retained REA
function dossier is `ev_931bf92d58c7106a382a89793c44f1a449547dd15df2b697589287a5b3134103`;
its recovered control flow is static analysis, not an execution trace.
[Sanitized receipt](video-gva-historical-selection-validation.json).
No proprietary binary is included in the repository.

```sh
R='/path/to/nvidia-880m-lab/bridge/results'
python3 bridge/experiments/video_gva_historical_selection/audit.py \
  --legacy "$R/video-enumeration-progress-20261018/AppleGVA-10.13.6-x86_64.private.macho" \
  --rea "$R/video-enumeration-progress-20261018/REA-legacy-gva.private.json" \
  --out "$R/historical-selection-new.json"
```

The conclusion is limited to the pinned historical function. It does not
establish current runtime causation, compatibility of old and new private
interfaces, a repair, hardware video execution or a performance gain.
