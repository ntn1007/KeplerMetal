# Refuse unmodeled indirect branches in CAS diagnosis

The offline CAS recognizer modeled direct `bra` and `joinat` targets but
previously ignored a register-indirect `bra` placed before the matched lock.
Its incoming-edge checks therefore could report a structural candidate without
knowing where that branch might enter. This is a diagnostic blind spot; the
experiment does not establish that the synthetic programs execute incorrectly
or that a real compiler emits them from the paired AIR.

The recognizer now refuses a `bra` or `joinat` spelling whose destination is
not a modeled direct literal, anywhere in the listing. The conservative rule
also refuses unsupported modifiers and potentially valid indirect flows. It
does not model every possible control-flow operation, establish register-indirect
branch semantics, or certify the shader for repair.

Three single-word variants of an archived NVIDIA program, at offset `0x238`,
were assembled with the pinned SM30 assembler and reproduced by the pinned
decoder: unconditional, positive-predicate and negative-predicate
`bra $r1 0x0`. All three were accepted by the recognizer at `21b8cb9` and
refused by the changed version. Three archived positive and one semantic
negative profile retain their prior verdicts with their exact decoder replayed.
The [sanitized receipt](cas-indirect-entry-validation.json) contains hashes and
verdicts only. The synthetic programs were not dispatched; unchanged AIR was
deliberately paired with altered code, so compiler correspondence is unproved.

The iMac offline suite passed 93 CAS tests. A further five parser-level branch
forms are exercised with placeholder instruction words; only the three variants
above were assembled and decoded. No existing certificate is regenerated, no
GPU repair is requalified, and no system component or installed driver changes.
Per-shader execution tests and independent semantic validation remain required.

## Reproduction

Use the retained private lab inputs, tools and a fresh output directory:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
OUT="$LAB/results/cas-indirect-entry-new"
mkdir "$OUT"
git show 21b8cb9:bridge/tools/recognize_native_cas.py > "$OUT/previous.py"
python3 bridge/tools/audit_cas_indirect_entry.py --previous "$OUT/previous.py" \
  --cases "$LAB/results/native-cas-conservative-qualification-20261027-01" \
  --assembler "$LAB/results/native-cas-repaired/envyas" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --out "$OUT/audit.json"
python3 -m unittest discover -s tests -p '*cas*.py'
```
