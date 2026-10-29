# Direct branches entering a CAS candidate

The offline native CAS recognizer previously searched linearly for a lock,
comparison and output sequence. It rejected selected post-repair backedges and
branches targeting the patch, but could still recognize a candidate when a
direct branch entered the sequence **after** its `ld lock`, bypassing the
operation whose value the repair assumes. It could also accept a branch into
the middle of the fixed lock/unlock sequence.

The recognizer now rejects direct branches that enter after the lock from
outside the lock-to-comparison interval, and any direct branch into the fixed
lock/unlock sequence after its first instruction. Targets that name a schedule
word are normalized to the next instruction, following the existing flow
tracer's convention. The checks are conservative and may refuse safe code;
they are not a complete Kepler control-flow or reconvergence model.

## Evidence and limits

The [offline audit](cas-incoming-branch-validation.json) assembles and decodes
four one-word synthetic mutations of an archived native program. They include
an unconditional jump to the later comparison, a conditional jump into the
lock sequence, a jump to a schedule word preceding the comparison, and a
loop branch into the fixed lock sequence. The previous full AIR/SASS diagnosis
accepted each as a candidate; the corrected diagnosis refuses each. The pinned
decoder reproduces each listing, which establishes consistency with that decoder,
not its semantic correctness.

The unchanged AIR and mutated NVIDIA code are deliberately paired and are
**not proven to come from the same compilation**. No synthetic program was
executed or repaired. Three previously captured candidates and one semantic
negative control retain their original verdicts. The prior GPU qualifications
and stored certificates are not silently regenerated, revoked or requalified.
The updated rule does not prove general alias, indirect-control-flow, barrier,
reconvergence or full program semantics; each actual shader still requires
separate qualification. It does not modify the installed compiler or imply a
performance gain.

The focused recognizer suite includes five text-level direct-branch controls;
all 88 CAS tests passed. The [receipt](cas-incoming-branch-validation.json)
contains source/tool fingerprints and candidate verdicts; proprietary shader
programs and local tools are not distributed.

## Reproduce

Use the retained local captures and pinned offline tools. No GPU operation is
issued. Choose a fresh output directory.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
D="$R/native-cas-conservative-qualification-20261027-01"
DEC="$LAB/build/envydis-only/envydis/envydis"
OUT="$R/cas-incoming-branch-new"
mkdir "$OUT"
git show 553fe08:bridge/tools/recognize_native_cas.py > "$OUT/previous_recognizer.py"
python3 bridge/tools/audit_cas_incoming_branch.py --previous "$OUT/previous_recognizer.py" --cases "$D" --assembler "$R/native-cas-repaired/envyas" --decoder "$DEC" --out "$OUT/audit.json"
python3 -m unittest discover -s tests -p '*cas*.py'
```
