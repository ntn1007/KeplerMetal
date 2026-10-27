# CAS diagnosis: complete and reproduced disassembly

The offline native-CAS recognizer now rejects missing, duplicate or reordered
instruction offsets. The prior implementation compared each displayed word to
the program and counted instructions, but did not require each offset to occur
exactly once in order. A duplicated line could therefore hide another line while
preserving the expected count.

A second counterexample kept the original offsets and raw words but replaced
the decoded operation text. Structural matching alone accepted that text. The
qualifying entry points now regenerate the complete listing from the exact
locally pinned `envydis` executable and require a byte-for-byte match before
accepting the SASS diagnosis. The decoder is copied to a temporary directory,
checked by SHA-256 before and after execution, and run with dynamic-loader
injection variables removed. A missing, changed, failed or different decoder
refuses qualification. The current pin is
`1c8730a9a4861f374c58407bff31d7ccb47a57eb23f9f82c6b3ea3deb079be0f`.
The executable is not distributed; a different build or version requires
separate qualification and cannot be silently repinned.

`recognize()` snapshots input bytes before diagnosis and records hashes of that
snapshot. The semantic reproduction checks that its code still matches the
diagnosed snapshot. The SDK preparation checks its diagnosed library and, for
candidates, its native program and metadata before building a certificate.
These are process-local checks, not a transactional filesystem or a defense
against an attacker controlling the tool, files, or process.

## Scope and evidence

The counterexample uses a previously created **synthetic one-instruction
modification** of an archived NVIDIA program. Its complete envydis listing
exposes an extra read of the register modified by the CAS repair. Replacing that
line with a duplicate of another genuine line made the prior recognizer accept
the SASS pattern. Replacing only the operation text, while retaining the raw
words and offsets, also made it accept the full prior AIR/SASS policy. Neither
altered listing was presented as real decoder output, and the modified program
was **never dispatched**. This does not demonstrate a defect in envydis or an
error in the archived GPU tests.

The new complete-offset check rejects the duplicate; the exact decoder replay
rejects both altered listings and refuses a missing decoder. Four previously
captured AIR/SASS cases retain their prior offline verdicts: three candidates
and one AIR semantic refusal. Twelve focused CPU tests cover line omissions,
reordering, duplicated schedule words, altered listings, missing or changed
decoders, environment filtering and input snapshot hashes. The
[machine-readable audit](cas-disassembly-integrity-validation.json) includes
fingerprints only, not proprietary code.

The pinned decoder is still a dependency: matching its output does **not** prove
that its decoded instruction semantics are correct. `sass_contract()` remains
a low-level structural parser and does not itself authenticate its text; do
not use its result alone to authorize a repair. AIR/source relationships,
control-flow and alias safety, trusted policy provenance, runtime conditions
and per-shader GPU correctness remain separate requirements. Existing stored
policies and SDK certificates are not invalidated by the runtime automatically;
regenerate them from actual inputs with the new tools before use. A subsequent [regenerated SDK cohort](CAS_SDK_REGENERATED.md) separately qualifies the tested shaders on the GTX. Earlier historical GPU results remain distinct. No installed
compiler, driver, Metal framework or OCLP component was modified.

## Reproduction

Choose fresh local paths. The archived fixtures and locally built decoder must
be obtained separately; this repository does not redistribute vendor binaries.
The historical recognizer from the last commit before this change is recovered
as source for an offline before/after comparison:

```sh
git show 2a1b5bd4ef054b3b0154b033fa56b570782660b8:bridge/tools/recognize_native_cas.py > "$LAB/results/previous-cas-recognizer.py"
python3 bridge/tools/audit_cas_disassembly_integrity.py \
  --previous-recognizer "$LAB/results/previous-cas-recognizer.py" \
  --cases "$LAB/results/native-cas-conservative-qualification-20261027-01" \
  --consumer-code "$LAB/results/cas-consumer-offline-20261027-01/consumer.sass" \
  --consumer-listing "$LAB/results/cas-consumer-offline-20261027-01/consumer.asm" \
  --decoder "$LAB/build/envydis-only/envydis/envydis"
python3 -m unittest discover -s tests -p test_native_cas_recognizer.py -v
```

For new diagnoses, the `recognize_native_cas.py` CLI now requires `--decoder`.
The compiled-library planner and reproduction runner use the qualified decoder
in their existing laboratory build path. Regenerate candidates and separately
qualify every intended shader on the target GPU; no benchmark or deployment is
implied by an offline PASS.
