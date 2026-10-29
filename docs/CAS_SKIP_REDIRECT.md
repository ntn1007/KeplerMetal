# Reject direct branches bypassing the CAS repair

The offline SASS recognizer previously accepted a forward branch between its
matched lock sequence and the redirect when the branch targeted the output
store after that redirect. Such a path could bypass the proposed correction.
The recognizer now conservatively refuses direct branches from the lock region
to a point after the redirect, including conditional branches. This may reject
safe paths: it is not a full Kepler control-flow proof.

Three one-word modifications of a retained NVIDIA program were assembled and
decoded with the pinned local tools: an unconditional branch and both predicate
forms, from `0x2a0` to the output store at `0x328`. All three were structurally
accepted by `f4dfb60` and refused by the updated recognizer. The unmodified
source remained structurally accepted by both. The [sanitized audit](cas-skip-redirect-validation.json)
records fingerprints and verdicts. The modified instructions were **not**
executed, and no compiler correspondence between their SASS and the unchanged
AIR is claimed. Reproduction by the pinned decoder is not proof of decoder or
hardware semantics.

An independent local comparison of four retained parsed AIR and SASS listings
found unchanged AIR/SASS verdict pairs: three positive pairs and one AIR
semantic negative with a positive SASS pattern. This comparison did not rerun
the decoder on those four files. The focused iMac suite passed 23 tests; the
full 92-test CAS suite passed on an arm64 MacBook using a tracked snapshot of
`f4dfb60` with the modified source and test verified by SHA-256. The original
iMac GPU debugger and a separate CPU guard test remain live; neither was
interrupted or rerun. No GPU qualification, certificate, system component or
installed driver was changed.

## Reproduction

Use the retained private program and offline tools, with a fresh output path.
The audit requires the exact previous recognizer and pinned binaries; no GPU
launch is performed.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
OUT="$LAB/results/cas-skip-redirect-new"
mkdir "$OUT"
git show f4dfb60:bridge/tools/recognize_native_cas.py > "$OUT/previous.py"
CASE="$LAB/results/native-cas-conservative-qualification-20261027-01/slot1"
python3 bridge/tools/audit_cas_skip_redirect.py --previous "$OUT/previous.py" \
  --source "$CASE/native.sass" --listing "$CASE/native.asm" \
  --assembler "$LAB/results/native-cas-repaired/envyas" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --out "$OUT/audit.json"
python3 -m unittest discover -s tests -p 'test_native_cas_recognizer.py'
python3 -m unittest discover -s tests -p '*cas*.py'
```

Per-shader validation and actual hardware tests remain necessary; this guard
does not repair the installed compiler or establish a performance gain.
