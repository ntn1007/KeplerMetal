# Conservative AIR output-path guard for native CAS

The offline CAS recognizer previously checked that the expected-pointer load
immediately followed the CAS in the same AIR block, but did not require the
output-vector insertion and final device store to remain on that same path.
It could therefore report a candidate when those operations were described as
belonging to another block. The recognizer now requires the insertion and
store to follow the load in the same straight-line block and rejects modeled
terminators in between. It does not attempt to prove dominance across blocks;
some safe shaders may consequently be refused.

The [offline audit](cas-air-output-path-validation.json) compares the previous
source at `6058b18` with this change. Three previously accepted parsed AIR
captures retain their verdicts and components; one prior semantic control
remains refused. For each accepted capture, two copies of the **parsed JSON**
move the insertion or store to another block. The previous recognizer accepts
all six; the revised recognizer refuses them. These edits are diagnostic
counterexamples, not compiled AIR or proof that each mutated graph is valid.
No mutated program is submitted to a GPU.

The focused iMac Python suite passed 22 tests. The complete 91-test CAS suite
passed on an arm64 MacBook using a tracked-source snapshot at `6058b18` plus
the two modified files, whose SHA-256 values were verified after transfer.
The full iMac suite did not finish: an unrelated CPU-only guard executable
remained in uninterruptible state while it was running. It was not counted as
a pass. Neither result establishes GPU correctness or requalifies an existing
certificate. No system component is changed and no shader is repaired here.

## Reproduction

Use the retained private captures and a fresh output directory. The audit reads
their parsed JSON; it does not execute a driver or send work to the GPU.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
OUT="$LAB/results/cas-air-output-path-new"
mkdir "$OUT"
git show 6058b18:bridge/tools/recognize_native_cas.py > "$OUT/previous.py"
python3 bridge/tools/audit_cas_air_output_path.py --previous "$OUT/previous.py" \
  --cases "$LAB/results/native-cas-conservative-qualification-20261027-01" \
  --out "$OUT/audit.json"
python3 -m unittest discover -s tests -p 'test_native_cas_recognizer.py'
python3 -m unittest discover -s tests -p '*cas*.py'
```

This guard does not prove general AIR/SASS correspondence, resource aliasing,
control-flow equivalence or the correctness of the NVIDIA driver. Per-shader
qualification and independent GPU validation remain necessary.
