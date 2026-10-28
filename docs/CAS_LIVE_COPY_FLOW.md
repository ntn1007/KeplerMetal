# Offline copied-lock CAS register-flow analysis

`bridge/tools/trace_native_cas_flow.py` identifies a **hypothesis**, not an
executable repair. It replays the pinned decoder and checks the retained AIR
diagnosis and native-code fingerprints. Within a bounded slice after a lock
loop and `join nop`, it follows direct branches and computes registers that
must contain the lock result on every modeled path. The analysis intersects
facts at joins, iterates loops to a fixed point, drops overwritten register
lanes, and recognizes an unconditional scalar register copy. It refuses
unsupported instruction effects, escapes, external branch entries, a changed
comparison input and reconvergence targets inside the tracked slice. It also
checks the output store and the proposed displaced constant-bank move.

On the previously GPU-qualified captured shader, this analysis recovers the
lock result in register 6, its saved copy in register 5, the comparison input
in register 0 and the proposed redirect at `0x530`. The modeled slice covers
47 instruction positions and 51 direct edges. This agrees with the earlier
[exact-profile experiment](CAS_LIVE_COPY_SDK.md); it is not a new GPU test or
independent proof that the same relation holds for all lanes.

The model begins **after** the reconvergence instruction with the entry facts
assumed. It does not prove that every relevant lane executed the CAS or that
Kepler reconvergence semantics are correctly modeled. The pinned decoder's
output, instruction scheduling, implicit state, AIR-to-SASS provenance and
memory aliasing also remain separate questions. An entry-target `joinat` is
explicitly permitted as an assumption, while targets inside the slice are
refused. The tool never generates a certificate, changes the SDK's exact
profile pin, patches a program or dispatches GPU work. Do not promote its
output directly to a runtime policy.

## Offline checks

Seven one-instruction synthetic mutations of the retained native program are
assembled and decoded offline. They include a skipped copy, wrong source,
overwritten saved or comparison register, an internal `join`, an external
jump into the slice and another use of the output register. All are refused.
The original AIR is deliberately paired with mutated code: no matching
compilation or GPU execution is claimed. Four other captured programs are
also refused by this specific constant-move hypothesis; this does **not**
mean those programs are defective or unsupported by other qualified paths.
Twelve CPU graph tests cover branch merges, loops, predication, vector writes,
unsupported controls and reconvergence entry. The broader CAS test suite
passed 47 tests. [Sanitized audit](cas-livecopy-flow-validation.json).

## Reproduce

The retained local diagnosis and pinned offline tools are prerequisites from
the [SDK experiment](CAS_LIVE_COPY_SDK.md). Their code and binaries are not
redistributed. Use fresh output paths. No GPU work is issued:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
DIAG="$LAB/results/cas-dynamic-overlay-20261028-01/results/dynamic-checked-diagnosis"
DECODER="$LAB/build/envydis-only/envydis/envydis"
python3 bridge/tools/trace_native_cas_flow.py --diagnosis "$DIAG" --decoder "$DECODER" \
  --out "$LAB/results/cas-livecopy-flow-new.json"
python3 bridge/tools/audit_cas_livecopy_flow.py --diagnosis "$DIAG" \
  --assembler "$LAB/results/native-cas-repaired/envyas" --decoder "$DECODER" \
  --out "$LAB/results/cas-livecopy-flow-audit-new.json"
python3 -m unittest discover -s tests -p '*cas*.py' -v
```
