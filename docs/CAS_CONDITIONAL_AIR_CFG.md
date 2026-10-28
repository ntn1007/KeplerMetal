# Conditional CAS AIR control-flow observation

The previous typed AIR dump omitted `air_inst.blocks`, although the retained
OpenNVDA AIR reader stores branch targets and PHI predecessor IDs there. The
new offline reader emits these IDs without changing the existing dump or the
repair recognizer. Removing the new fields reproduces the earlier typed dump
exactly for this capture. Both dumps depend on the same reader implementation;
this is a consistency check, not an independent verification of AIR decoding.

For the pinned `divergence_case` capture, the augmented dump describes 12
blocks and 19 edges. The expected value is initialized in instruction 48,
CAS appears at 49, and the expected pointer is loaded at 51 in block 8. Block 8
branches to block 9, whose PHI at 55 selects that load on the edge from block 8
and the initialized value on the edge from block 7. Its result is inserted at
instruction 61, component 0. This explains why the existing recognizer, which
requires a direct load-to-insertion, refuses the profile.

The offline inspector checks the earlier dump projection, graph structure,
PHI predecessor sets, the specific initializer/load/PHI pattern and insertion.
Synthetic tests reject wrong PHI edges, swapped values, a changed fallback,
invalid branches, missing block information, changed prior evidence and an
invalid index. These are parser-level checks and were never sent to the GPU.

**This observation authorizes no repair.** It does not establish alias safety,
dominance for all values, the complete path to the device output, predicate
semantics, or the native SASS register and control flow. The separate native
indirect-branch obstacle remains. Neither the existing AIR recognizer nor the
SDK gate was relaxed. Two source rebuilds produced the same augmented AIR hash;
no GPU work or performance measurement was performed.

[Reproduction evidence](cas-conditional-air-cfg-validation.json) ·
[Existing exact-profile GPU qualification](CAS_DIVERGENCE_SDK.md)

## Reproduction

The local retained AIR, prior typed dump, OpenNVDA header and object files are
fingerprinted by the reproducer. The captures remain local; the header and
objects must be obtained or built locally. The object fingerprints establish identity only, not their
correspondence to a particular source commit. A changed input needs review.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
python3 "$REPO/bridge/experiments/cas_divergence/reproduce_air_cfg.py" \
  --lab "$LAB" --out "$LAB/results/cas-divergence-cfg-new"
python3 -m unittest discover -s "$REPO/tests" -p 'test_cas_conditional_air_cfg.py' -v
```

The full augmented dump remains local. The published evidence contains only
structural observations and fingerprints; no captured NVIDIA program is
published.
