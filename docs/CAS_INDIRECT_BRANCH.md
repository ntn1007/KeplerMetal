# Conditional CAS indirect branch: candidate table

The captured NVIDIA program contains a register-indirect branch at `0x290`.
The pinned decoder shows an unsigned minimum by 2 followed by a shift by 2,
then `ld b32 $r1 c0[$r0]` and `bra $r1 0x0`. **If the displayed index sequence
executes as decoded**, the byte index at the load is one of 0, 4 or 8. A scan
of decoded direct `bra` and `joinat` literal targets finds no direct entry
into `0x270..0x290`; this scan does not establish all control-flow entries or
SIMT reconvergence behavior.

The same captured compiler-output container has a 12-byte section of type
`0x10006`. Its three little-endian words are `0x298`, `0x2b8` and `0x330`,
each corresponding to a decoded instruction offset in the same program. This
is a **candidate table**, not proof that the runtime binds that section as
`c0`, or that the indirect branch interprets its words as absolute program
offsets. Those properties require separate evidence. No GPU command was
submitted by this analysis, and the capture did not read back resident GPU
instructions.

The original SDK import checked the live code and metadata but did not pin the
auxiliary section. The [new exact-profile guard](CAS_CONDITIONAL_AUX_GUARD.md)
checks that the live constructor input contains exactly one 12-byte `0x10006`
section with the qualified SHA-256 before substituting the program. A mismatch
leaves the original constructor input untouched and rejects the experimental
pipeline before a user GPU dispatch. This does not prove that the section is
actually bound to `c0` or widen the recognizer. Do not assume that a library
hash alone proves the compiler's auxiliary output.

The offline inspector checks the retained container fingerprint, sections,
exact code and pinned decoder replay. Synthetic tests reject altered table
words, truncated containers, different load/index/branch instructions,
extra indirect branches and selected direct entries. None of those synthetic
programs are sent to the GPU. [Sanitized observation](cas-indirect-validation.json).

## Reproduction

The original compiler output, code and decoder remain in the local lab and
are not redistributed. Inputs are fingerprinted; do not silently repin a
different capture.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
python3 "$REPO/bridge/experiments/cas_divergence/analyze_indirect.py" \
  --container "$LAB/results/cas-divergence-capture-20261028-01/capture/program-0.compiler-output.bin" \
  --code "$LAB/results/cas-divergence-capture-20261028-01/native.sass" \
  --listing "$LAB/results/cas-divergence-analysis-20261028-01/native.asm" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" \
  --out "$LAB/results/cas-divergence-indirect-analysis-new.json"
python3 -m unittest discover -s "$REPO/tests" -p 'test_cas_indirect_branch.py' -v
```
