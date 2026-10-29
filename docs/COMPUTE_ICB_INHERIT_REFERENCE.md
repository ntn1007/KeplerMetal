# Native compute ICB pipeline inheritance reference

The scoped KeplerMetal compute adapter currently refuses an indirect command
buffer with `inheritPipelineState = YES`. Apple documents that an indirect
compute command can take its pipeline from the parent compute encoder when the
descriptor requests inheritance: [setComputePipelineState](https://developer.apple.com/documentation/metal/mtlindirectcomputecommand/setcomputepipelinestate%28_%3A%29)
and [MTLIndirectComputeCommand](https://developer.apple.com/documentation/metal/mtlindirectcomputecommand).
This reference characterizes one such case; it does not implement the feature
on Kepler.

The standalone [public Metal client](../bridge/experiments/metal_compute_inherited_reference/reference.mm)
creates one native compute ICB with inherited pipeline state and an explicit
output buffer. The same command is executed across three serial encoders whose
parent pipeline selection is A, B, A. A and B write distinguishable values;
each corresponding direct dispatch is checked against a CPU oracle. No pipeline
setter is called on the indirect command. A no-dispatch command buffer is a
separate negative control.

On an Apple M1 Max, macOS 27.2 build 26B123, a signed arm64 process completed
with SSH exit code 0. Six dispatches generated 384 correct uint32 values; the
64-word control stayed at its initial value. Three direct/ICB output pairs were
byte-identical, with A and B producing different bytes. The executable and
source hashes were checked on the remote host before and after the run. All
seven captures and both logs were copied to the iMac and matched the remote
SHA-256 values. A separate [offline auditor](../bridge/experiments/metal_compute_inherited_reference/audit.py)
rechecks all words, hashes and the control; its [sanitized receipt](compute-icb-inherit-m1-validation.json)
does not expose a device registry identifier. A mutation test rehashes altered
copies and confirms refusals for incorrect matching A/B output, a changed blank
control and a changed report. The captured raw data and remote executable remain
in the private lab or remote temporary directory, not this repository.

An earlier exploratory M1 run also exited 0 but was not included in these
counts because it did not retain raw captures. The audited run uses one process
and one command slot. It does not test reset, multiple commands, inherited
buffers, invalid pipelines, multithreaded encoding, multiple GPU queues,
pipeline-state preservation after execution or performance. It establishes an
Apple Silicon reference, not execution on the GTX or a transparent macOS driver
feature. Its independently compiled source and binary are pinned in the auditor;
a later build has a different identity and requires a new verification record.

## Consequence for the scoped adapter

The current `createICB` rejects compute pipeline inheritance, while
`concurrentDispatchThreadgroups` currently obtains its limits from a pipeline
already set on the command. Supporting this reference case therefore requires
tracking the parent encoder pipeline and validating its registered profile,
bindings, dimensions and limits at execution time. Materialized command caches
must be invalidated or keyed by the inherited pipeline and must preserve the
parent encoder's state. GPU-generated, partial-grid and reusable-command paths
need their own contracts; this single reference does not qualify them.

Next, create a scoped implementation and same-source direct/indirect GTX tests
with A/B/A switches, stale-cache and unregistered-pipeline refusals, followed by
state-restoration and lifetime tests. The iMac GPU runs remain pending an
unlocked graphical session. No driver or system file was changed here.

## Reference build and retained-input audit

On an appropriately provisioned Mac with a fresh output directory:

```sh
xcrun clang++ -arch arm64 -std=c++17 -fobjc-arc -framework Foundation -framework Metal \
  bridge/experiments/metal_compute_inherited_reference/reference.mm -o "$OUT/reference"
codesign --force --sign - "$OUT/reference"
mkdir "$OUT/captures"
"$OUT/reference" "$OUT/captures" > "$OUT/stdout.json" 2> "$OUT/stderr.log"
```

The shipped auditor is pinned to this specific retained run and its transferred
`remote-hashes.json`; a fresh compilation must not silently reuse those pins.
For the retained lab directory, run:

```sh
python3 bridge/experiments/metal_compute_inherited_reference/audit.py \
  --input /path/to/retained-reference --out /path/to/fresh-audit.json
python3 bridge/experiments/metal_compute_inherited_reference/test_audit_mutations.py \
  --input /path/to/retained-reference
```
