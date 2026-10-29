# Refuse unmodeled reconvergence past the CAS redirect

The offline CAS recognizer refused ordinary branches that could bypass the
repair redirect, but it could still accept a `joinat` established between the
matched lock and redirect with a target after that redirect. Since the SIMT
reconvergence stack is not modeled, this target cannot safely be treated as
irrelevant. The recognizer now conservatively refuses that structural pattern,
including targets at schedule words normalized to the next instruction.
This does not prove that a particular lane reaches the target, that an NVIDIA
compiler emits these synthetic programs, or that complete SIMT control flow is
modeled. Some safe programs may be refused.

Three variants modify one word at `0x2a0` in the retained NVIDIA program;
the pinned assembler and decoder confirm `joinat 0x2f8`, `joinat 0x300` and
`joinat 0x328`. The recognizer at `f4c6b64` accepted each and the updated one
refused each. `0x300` is a schedule word and normalizes to `0x308`; `0x328`
is the output store in this captured program. Three archived positive and one
semantic negative profile retained their outcomes with decoder replay. The
[sanitized receipt](cas-reconvergence-bypass-validation.json) contains only
hashes and verdicts. The variants were never sent to a GPU and their unchanged
AIR was not shown to produce their modified SASS.

The iMac CPU suite passed 94 CAS tests. Predicated variants in the unit tests
are decoder-shaped parser controls with placeholder words, not assembled or
GPU-executed shaders. This change neither requalifies existing certificates nor
repairs the installed compiler. Per-shader qualification remains necessary.

## Reproduction

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
OUT="$LAB/results/cas-join-bypass-new"
mkdir "$OUT"
git show f4c6b64:bridge/tools/recognize_native_cas.py > "$OUT/previous.py"
python3 bridge/tools/audit_cas_join_bypass.py --previous "$OUT/previous.py" \
  --cases "$LAB/results/native-cas-conservative-qualification-20261027-01" \
  --assembler "$LAB/results/native-cas-repaired/envyas" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --out "$OUT/audit.json"
python3 -m unittest discover -s tests -p '*cas*.py'
```
