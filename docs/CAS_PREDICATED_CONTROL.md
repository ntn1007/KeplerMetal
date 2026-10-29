# Predicated control flow in the offline CAS hypothesis

The copied-lock CAS flow analyzer previously stripped predicates when it
computed register writes, but tested some control instructions against the
original, still-predicated text. Consequently, a conditional `exit`, `join`
or `joinat` could be treated as an ordinary fall-through in a slice that the
model claims to keep free of such control flow. A predicated `joinat` outside
the slice could also be missed. This could produce a **hypothesis** based on
an incomplete control-flow model.

The analyzer now checks the opcode after removing the predicate. It refuses
`join`, `joinat` and `exit` inside the tracked slice whether predicated or not;
it also refuses any predicated `joinat` because this analysis does not model
predicate-dependent reconvergence. The earlier explicit assumption for an
unpredicated reconvergence target at the slice entry remains. No repair,
certificate or GPU dispatch is authorized by this analysis.

## Evidence and limits

The [offline counterexample audit](cas-predicated-control-validation.json)
replaces one word at offset `0x3d8` in a previously captured native program
with either `$p1 exit` or `(not $p1) exit`, using the pinned local assembler.
The pinned decoder reproduced both instructions and the complete modified
listings. The previous analyzer produced `HYPOTHESIS_ONLY` for both; the updated
analyzer refuses both. The AIR was retained from the original program, so a
compiler relationship between that AIR and the synthetic SASS is **not**
proved. Neither synthetic program was executed. Decoder identity does not prove
decoder semantics.

The original captured program's analysis is unchanged. A separate
[regression](cas-predicated-control-regression.json) preserved its previous
hypothesis, refused four other captured inputs and refused the seven existing
synthetic mutations. Fourteen focused graph tests include both predicate forms
for `join`, `joinat` and `exit`; these text-level tests do not establish that
all such forms can be encoded on hardware. The full CAS test selection passed
87 tests. Existing exact-profile GPU results and certificates are not silently
requalified or revoked; this change does not fix the installed NVIDIA compiler,
prove arbitrary shader safety or establish a performance gain.

## Reproduce

The retained diagnosis and pinned assembler/decoder are local and are not
redistributed. The previous analyzer is taken from the pre-change Git commit.
Use a fresh output location. These commands do not use the GPU.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
D="$R/cas-dynamic-overlay-20261028-01/results/dynamic-checked-diagnosis"
DEC="$LAB/build/envydis-only/envydis/envydis"
OUT="$R/cas-predicated-control-new"
mkdir "$OUT"
git show 2e0b767:bridge/tools/trace_native_cas_flow.py > "$OUT/previous_trace.py"
python3 bridge/tools/audit_cas_predicated_control.py --previous "$OUT/previous_trace.py" --diagnosis "$D" --assembler "$R/native-cas-repaired/envyas" --decoder "$DEC" --out "$OUT/audit.json"
python3 bridge/tools/audit_cas_livecopy_flow.py --diagnosis "$D" --assembler "$R/native-cas-repaired/envyas" --decoder "$DEC" --out "$OUT/regression.json"
python3 -m unittest discover -s tests -p '*cas*.py'
```
