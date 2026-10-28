# Conditional witness after AppleGVA constructor

The pinned selector dispatch calls the previously studied constructor, then
calls a routine at image offset 146236. Its normal path can call a deallocator
at offset 146305, returning to 146310, only if a temporary pointer is nonzero.
The local cache's rebased stub points to libc++abi `operator delete(void*)`;
runtime binding is not independently established for this call. REA/Ghidra
evidence `ev_860608ba616ed81bc7d6a881c19b0713b802a1fbcbe1b8fb1f5ebbb4935c37fa`
analyzes the 112-byte captured region (SHA-256
`38281d047ee261127550cff96495d8aa7a911fe889fb6f7a6ac2992f3bbb274c`).
It does not establish runtime execution or complete exception behavior.

Two current-board counterfactual H.264 processes recorded **zero** events at
that one callsite, with live SHA-256 checks of the selector and 146236 regions
and the expected deallocator implementation present. Both returned -12913 and
zero images. A same-host control without this witness returned the same status;
a wrong-board control returned -12906 and zero images. A software control
produced six frames matching 691,200 CPU-reference bytes.

**Zero events do not show that the constructor failed or succeeded.** The
deallocation is conditional, runtime interposition at this site is not proven,
and the callsite may be absent even when the routine executes. The previous
stack observation was taken inside the base initializer, not after it. None of
these tests demonstrates hardware video execution or a repaired driver.

The experimental observer interposes public `operator delete` only in its
own process, filters on the single return address, forwards the original
argument and does not dereference it. It validates two loaded code regions and
does not patch them or call a private function. In a separately compiled
calibration build of the same source, synthetic cross-image calls validate the
tail, argument, register and callsite filter; the test does not independently
prove actual memory deallocation. The calibration-only arming API is absent
from the production build. The scalar control exercises 256 register and flags
cases. The [audit receipt](video-gva-postconstructor-validation.json) records
the five terminal, nonoverlapping runs and hashes. No system driver or OCLP
change was made.

## Reproduction

Use the exact pinned profile, retained private lab fixtures and shared GPU
reservation. The runner refuses profile drift; use new paths and do not restart
an unresolved process. No proprietary binaries are supplied here.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
EXP=bridge/experiments/video_gva_postconstructor_witness
BASE="$R/gva-property-build-20261028-01"
BUILD="$R/gva-postconstructor-build-new"
CAL="$R/gva-postconstructor-calibration-new"
python3 "$EXP/cpu_calibration.py" --out "$CAL"
python3 "$EXP/experiment.py" build --lab "$LAB" --base "$BASE" --out "$BUILD"
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/post-cpu-new" --mode cpu --witness on
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/post-wrong-new" --mode wrong --witness on
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/post-current-1-new" --mode current --witness on
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/post-current-off-new" --mode current --witness off
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/post-current-2-new" --mode current --witness on
python3 "$EXP/audit.py" --base "$BASE" --build "$BUILD" --calibration "$CAL" \
  --runs "$R/post-cpu-new" "$R/post-wrong-new" "$R/post-current-1-new" "$R/post-current-off-new" "$R/post-current-2-new" \
  --out "$R/post-audit-new.json"
```
