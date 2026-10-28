# Conditional CAS: passive CB0 command observation

Four isolated, signed processes prepared an ordinary Metal command buffer on
the GTX 880M: two used the native conditional-CAS pipeline and two used the
explicitly adapted, guarded repaired pipeline. Each encoded one dispatch but
left its command buffer **not enqueued and not submitted**. The observer read
only its own process's established encoder/variant ABI fields and a bounded
snapshot of its own encoded commands. The shared cooperative reservation was
held for every process. No GPU execution or performance was measured here.

An offline packet decoder found one 256-byte QMD upload per capture. On all
four, the captured QMD reported CB-valid mask 7 and CB0 size 256 bytes. Its
CB0 GPU address equaled the native variant code address plus its code length
rounded up to 256 bytes. The QMD program low 32 bits and register count also
matched the variant. Native code length was 1,344 bytes; repaired length was
1,408 bytes. Both round to 1,536 bytes. The two repaired imports reported that
the live auxiliary-section guard passed.

This shows a prepared command's CB0 **address and extent**, not its contents.
It does not establish that the `0x10006` section was copied there, that the
indirect branch uses the candidate values as targets, or what code or data
resided in GPU memory. No GPU address was dereferenced as a host pointer and
no VRAM readback was attempted. Prior numerical GPU validation is separate.

The first native child exited successfully and released the reservation, but
its runner then failed a postcheck because of a singular/plural JSON key typo.
That runner error is preserved; the key was corrected for the next three
processes. The independent audit rereads the first child's unchanged raw files,
signature, terminal manifest and profile along with the other three. It passed
twice with identical results. Synthetic packet tests reject altered bank,
program, register, size, and duplicate/truncated QMD cases.
[Sanitized audit](cas-conditional-cb0-validation.json).

## Reproduce

Requires the retained local conditional SDK build and pinned iMac profile.
Captured command and variant bytes remain local; do not redistribute them.
The cooperative lease cannot exclude WindowServer or nonparticipating work.
Choose fresh paths and resolve any nonterminal process before another run.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
BASE="$LAB/results/cas-conditional-aux-build-20261028-02"
BUILD="$LAB/results/cas-conditional-cb0-build-new"
python3 "$REPO/bridge/experiments/cas_divergence/prepare_cb0.py" --lab "$LAB" --base "$BASE" --out "$BUILD"
for item in native:native1 repaired:repaired1 native:native2 repaired:repaired2; do
  mode=${item%:*}; label=${item#*:}
  python3 "$REPO/bridge/experiments/cas_divergence/run_cb0.py" --lab "$LAB" --build "$BUILD" \
    --out "$LAB/results/cas-conditional-cb0-$label-new" --mode "$mode"
done
python3 "$REPO/bridge/experiments/cas_divergence/audit_cb0.py" --build "$BUILD" \
  --runs "$LAB/results/cas-conditional-cb0-native1-new" "$LAB/results/cas-conditional-cb0-repaired1-new" \
  "$LAB/results/cas-conditional-cb0-native2-new" "$LAB/results/cas-conditional-cb0-repaired2-new" \
  --out "$LAB/results/cas-conditional-cb0-audit-new.json"
python3 -m unittest discover -s "$REPO/tests" -p 'test_cas_cb0_observation.py' -v
```
