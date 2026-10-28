# CAS diagnosis: writes combined with JOIN

The offline CAS recognizer tracks whether the registers used by its proposed
repair survive between the lock loop and a later comparison. NVIDIA SM30
disassembly can show a reconvergence modifier combined with an ordinary
instruction, for example `join mov b32 $r9 $r6`. The previous recognizer
treated every `join` as writing no general-purpose registers. It could therefore
accept a candidate whose lock-result register is overwritten in that interval.

The recognizer now analyzes the operation following `join`, including vector
register spans. An unrecognized combined operation is refused, and `join nop`
continues to have no register writes. This is a conservative correction to
the candidate filter, not a general proof of shader semantics.

## Evidence and limits

The offline audit replaces one instruction at `0x390` in a previously captured
native program with an assembler-produced `join mov b32 $r9 $r6`. The pinned
decoder reproduces the complete modified listing. The previous structural
recognizer accepts this synthetic program with `$r9` as the old value; the
updated recognizer rejects it. The original AIR and altered machine code are
deliberately paired for diagnosis and are **not proven to come from the same
compilation**. The modified program is never dispatched. This establishes a
filtering gap, not that the installed compiler emitted this combination or
that previous GPU results were incorrect.

Four original captured candidates and one original-comparand control retain
their earlier offline verdicts. The [sanitized audit](cas-join-write-validation.json)
records hashes rather than vendor instructions or binaries. Eighteen focused
CPU tests include an in-range vector write and an unknown combined operation.
No new GPU qualification, performance measurement, system modification, or
transparent application support is claimed. Existing certificates are not
automatically revoked: regenerate the diagnosis from exact inputs and qualify
each new shader on the target GPU before using it.

## Reproduction

Use the isolated lab and its previously generated dynamic-neighbor SDK inputs;
the NVIDIA code and locally built assembler/decoder remain on the machine. The
audit runs only the assembler and offline decoder, not a GPU dispatch. Select a
fresh output path and use the parent commit of this change as `BASE`.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
BASE='2ebf58c'
git show "$BASE:bridge/tools/recognize_native_cas.py" > "$LAB/results/recognizer-before-join.py"
python3 bridge/tools/audit_cas_join_write.py \
  --previous "$LAB/results/recognizer-before-join.py" \
  --generated "$LAB/results/cas-dynamic-neighbor-overlay-20261028-01/results/generated" \
  --assembler "$LAB/results/native-cas-repaired/envyas" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" \
  --out "$LAB/results/cas-join-write-audit-new.json"
python3 -m unittest discover -s tests -p 'test_native_cas_recognizer.py' -v
```
