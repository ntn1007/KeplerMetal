# Reconvergence targets in the native CAS recognizer

The offline AIR/SASS recognizer already rejects direct branches entering the lock-to-comparison interval, but `joinat` targets were only included in checks at the patch and in backedge checks. In the pinned decoder's output, a separate reconvergence target can therefore enter that interval without triggering those checks. The previous recognizer accepted the five synthetic variants below; this is evidence of a structural blind spot, not proof that those synthetic shaders actually misexecute.

The revised recognizer checks `joinat` destinations after normalizing a target at a schedule word to the next executable instruction. It rejects targets inside the interval except for a single observed pattern: one `joinat` before the lock targets the instruction following the `join nop` immediately after the retry. This retains the archived profiles, but **assumes** that this pattern is safe; it does not establish the Kepler reconvergence stack, reachability or the origin of all active lanes. Other unsupported reconvergence contexts remain a reason for per-shader qualification. Predicated spellings are checked by parser-level tests; the pinned assembler did not accept the probed predicated `joinat`, so these tests make no hardware-encoding claim.

## Evidence

The [offline audit](cas-reconvergence-validation.json) changes one word in a captured NVIDIA program for each variant. The pinned assembler emits, and the pinned decoder reproduces, targets at the later comparison, the lock sequence, a schedule word preceding the comparison, a target from the loop and a second target matching the existing reconvergence point. All five have `qualified: true` under commit `dd471fa` and `qualified: false` under this change. Three captured candidates retain their prior positive structural verdict and one AIR semantic control retains its negative verdict. The test suite passes 89 CAS tests.

The synthetic code was paired with unchanged AIR and was **not** shown to originate from that AIR, submitted to the GPU or repaired. The decoder's reproduction does not establish its semantics. Prior exact-profile GPU observations remain historical results; existing certificates are not silently regenerated or requalified. This guard does not implement a complete control-flow model, prove general CAS repair, modify the installed compiler or establish a performance gain.

## Reproduce

Use retained local archives and pinned offline tools; no GPU work is performed. Choose a fresh output path.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
OUT="$R/cas-reconvergence-new"
mkdir "$OUT"
git show dd471fa:bridge/tools/recognize_native_cas.py > "$OUT/previous_recognizer.py"
python3 bridge/tools/audit_cas_reconvergence.py \
  --previous "$OUT/previous_recognizer.py" \
  --cases "$R/native-cas-conservative-qualification-20261027-01" \
  --assembler "$R/native-cas-repaired/envyas" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" \
  --out "$OUT/audit.json"
python3 -m unittest discover -s tests -p '*cas*.py'
```
