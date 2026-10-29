# Refuse unmodeled GK104 control operations in CAS diagnosis

The CAS recognizer models a restricted set of direct branches and one assumed
reconvergence shape. It previously ignored several other operations that the
pinned GK104 decoder names in its control-instruction table, including return,
break/continue and preparation of control-stack targets. The recognizer now
refuses those operation names anywhere in the listing, as well as unmodeled
call, execution-mask and trap operations. This is deliberately conservative:
not every occurrence is a defect and valid programs may be rejected. The rule
does not prove complete decoding, SIMT behavior, reachability or the absence of
other unmodeled operations.

The local envytools reference is the checkout labeled
`f102b82381f3f11cee113d16374c87091db039d9`; the inspected
`envydis/gf100.c` SHA-256 is
`6277a1f43c6d4216e53c12ec4a7464eb9d1ce65420a8293280c56d0eb8fa46e0`.
It is used to identify decoder operation names, not to infer complete hardware
semantics. The audit uses the previously pinned assembler and decoder binaries.

Ten one-word variants were assembled at `0x238` before the matched CAS lock:
`prelongjmp`, `prebrk`, `precont`, `preret`, `longjmp`, `ret`, `brk`, `cont`,
`rtt` and `discard`. The pinned decoder reproduced each instruction. The
recognizer at `17dbc8f` accepted the ten altered inputs; the changed version
refuses them. Three archived positive profiles and one semantic negative retain
their verdicts with the decoder replayed. The [sanitized receipt](cas-unmodeled-control-validation.json)
records fingerprints and verdicts only. Unchanged AIR was paired with modified
SASS, so no compiler correspondence is established. None of the variants was
executed on the GPU; their actual reachability and consequences are unknown.

The iMac offline suite passed 95 CAS tests. Additional parser-only cases cover
`call`, quad-mode operations, trap and selected predicated forms; these cases
use placeholder words and do not establish their hardware encodings. No
certificate was regenerated, no repair requalified and no system component
changed. Independent per-shader numerical GPU qualification is still required.

## Reproduction

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
OUT="$LAB/results/cas-unmodeled-control-new"
mkdir "$OUT"
git show 17dbc8f:bridge/tools/recognize_native_cas.py > "$OUT/previous.py"
python3 bridge/tools/audit_cas_unmodeled_control.py --previous "$OUT/previous.py" \
  --cases "$LAB/results/native-cas-conservative-qualification-20261027-01" \
  --assembler "$LAB/results/native-cas-repaired/envyas" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --out "$OUT/audit.json"
python3 -m unittest discover -s tests -p '*cas*.py'
```
