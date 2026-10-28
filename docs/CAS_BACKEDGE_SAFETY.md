# Native CAS diagnosis: post-repair backedges

The offline CAS recognizer now refuses a decoded `bra` or `joinat` located after the proposed redirect when its target is at or before that redirect. Such a path could revisit the lock/compare region after the repair has changed the expected-value register. The rule is conservative: it can reject unreachable or otherwise safe paths, and is not a full control-flow or dataflow proof.

## Evidence

A local **synthetic** counterexample changes one eight-byte instruction of the archived `slot1` SASS program at `0x2d8` into `bra 0x250`, targeting the lock instruction after the proposed redirect at `0x2d0`. The local assembler produced the branch; the pinned offline decoder reproduced the complete modified listing. Given the original fixture's AIR and the modified SASS, the previous full diagnosis accepted the pair; the updated diagnosis refuses it. The unchanged AIR and modified SASS are deliberately paired for the experiment and are **not proven to come from the same compilation**. Neither the modified program nor a repaired version was dispatched. There is no evidence that the native compiler emitted this case or that a historical GPU-qualified shader is defective.

The same before/after audit rechecks four archived AIR/SASS fixtures: the three prior candidates remain accepted and the original-comparand semantic control remains rejected. Fourteen focused CPU tests pass, including synthetic conditional and unconditional backedges before and after the output store. Historical GPU qualifications remain their own evidence; this change has not been newly qualified by a GPU run.

The decoder replay authenticates a pinned listing, not decoder semantics or AIR-to-SASS provenance. This new rule does not address indirect jumps, every possible branch interaction, register aliases beyond the existing checks, memory aliasing or arbitrary shaders. Existing stored policies and SDK certificates are not automatically revoked. Regenerate and qualify a policy from actual matched inputs before use; do not deploy the synthetic shader or infer a general compiler repair.

## Reproduction

Use the existing isolated lab, exact archived fixtures and locally built assembler/decoder. Vendor programs and compiled tools are not distributed. Choose new paths. The assembler and decoder invocations below use the existing signed-process runner and shared reservation; they do not dispatch GPU work. Check that each process is terminal before continuing.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
OUT="$LAB/results/cas-backedge-new"
mkdir "$OUT"
git show bb937d8c3289e69d9c9d30b47b58e5246933ec1c:bridge/tools/recognize_native_cas.py > "$OUT/previous-recognizer.py"
printf '.section #code 0;\n.skip 0x2d8;\nlong bra 0x250;\n' > "$OUT/branch.easm"
python3 "$LAB/tools/run_signed_probe.py" --exe "$LAB/results/native-cas-repaired/envyas" \
  --out "$OUT/assemble-execution" --timeout 20 -- -m gf100 -V gk104 -i \
  -o "$OUT/branch.bin" "$OUT/branch.easm"
python3 - "$LAB" "$OUT" <<'PY'
from pathlib import Path
import sys
lab,out=map(Path,sys.argv[1:])
original=(lab/'results/native-cas-conservative-qualification-20261027-01/slot1/native.sass').read_bytes()
assembled=(out/'branch.bin').read_bytes()
assert len(original)==832 and len(assembled)>=0x2e0
modified=bytearray(original);modified[0x2d8:0x2e0]=assembled[0x2d8:0x2e0]
assert modified!=original
(out/'backedge.sass').write_bytes(modified)
PY
python3 "$LAB/tools/run_signed_probe.py" --exe "$LAB/build/envydis-only/envydis/envydis" \
  --out "$OUT/decode-execution" --timeout 20 -- -m gf100 -V gk104 -i -n "$OUT/backedge.sass"
python3 bridge/tools/audit_cas_backedge.py --previous "$OUT/previous-recognizer.py" \
  --cases "$LAB/results/native-cas-conservative-qualification-20261027-01" \
  --code "$OUT/backedge.sass" --listing "$OUT/decode-execution/execution.stdout" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --out "$OUT/audit.json"
python3 -m unittest discover -s tests -p test_native_cas_recognizer.py -v
```

[Sanitized validation record](cas-backedge-validation.json). No system driver, Metal framework or OCLP component was modified.
