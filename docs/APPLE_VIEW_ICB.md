# Apple shader ICB with BGRA color and depth attachment

The scoped CPU ICB accepts a second exact profile for the pinned Apple sample
shader: a 64×48 `BGRA8Unorm` color target and `Depth32Float` attachment. The
test sets back-face culling and executes 15 commands with explicit vertex
buffers, inherited pipeline state and two frame-state generations. A private
frame buffer is populated by an earlier blit in the same command buffer in
half of the cases. The color format corresponds to the documented
[MTKView default](https://developer.apple.com/documentation/metalkit/mtkview/colorpixelformat);
the Apple sample sets the depth format and back-face culling in its source.

This is still a synthetic offscreen scene with an application-local adapter,
not the Apple application, an MTKView drawable or transparent macOS support.
The exact shader, target dimensions and descriptor are pinned. Resizing,
other profiles, overlapping frames and GPU-encoded ICBs remain unqualified.

## Evidence and failure investigation

Two direct/adapted pairs on the GTX produced 16 completed render buffers. The
[auditor](apple-view-icb-validation.json) compares 196,608 raw color bytes,
8,192 guard bytes and 240 expected center pixels, and checks 120 adapted draw
packets and their resource metadata. Images match direct rendering, including
the pre-change direct reference. Updating the frame changes the image; shared
and private variants match. A short object buffer at the last slot is refused
before submission in both adapted runs. The first 14 slots were materialized
into unsubmitted intermediate records; CPU-side rollback is not claimed.

The previous runtime refused this exact profile. An initial candidate then
stopped before submission and the test process aborted because an exception
released an unended encoder. A guarded diagnostic subsequently ended the
encoder and exposed the underlying `Unexpected stage-in native state prefix`
refusal. Two separate, unsubmitted native observations found the same
first-draw prefix in each run, with distinct first words for cull-none and
cull-back. The runtime now accepts only those exact observed word sequences
for the pinned view profile and preserves the prefix; the final auditor checks
the actual copied draw and retained prefix. It does not infer the meaning of
every prefix bit.

Positive images confirm rendering with the configured depth attachment and
back-face cull state. They do **not** independently prove depth-test behavior or
that reversed faces are rejected: no such negative controls were run. A
missing-blit negative control and overlapping-frame tests also remain open.
Signed process outcomes, nonoverlapping GPU reservations and selected system
hashes were checked; no performance comparison was made.

The same archive passes the earlier [explicit-buffer](apple-view-icb-explicit-regression.json)
and [inherited-pipeline](apple-view-icb-inherited-regression.json) regressions.

## Reproduce

Obtain the exact local Apple library and carrier as described in
[the sample analysis](APPLE_CPU_ICB_GAP.md). Use fresh outputs and establish
the terminal state of any uncertain process before retrying. The auditor also
needs the recorded pre-change direct/refusal, prefix-observation and diagnostic
runs; their arguments are shown explicitly so prior failures are not silently
recreated or rewritten.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
OLD_BUILD='/path/to/recorded-pre-change-build'
OLD_DIRECT='/path/to/recorded-pre-change-direct'
OLD_AUTO='/path/to/recorded-pre-change-refusal'
EARLY='/path/to/recorded-encoder-assertion'
DIAGNOSTIC='/path/to/recorded-prefix-refusal'
PREFIX_BUILD='/path/to/recorded-prefix-build'
PREFIX1='/path/to/recorded-prefix-run-1'
PREFIX2='/path/to/recorded-prefix-run-2'
python3 tools/build_from_source.py --out build/apple-view-new
A="$PWD/build/apple-view-new"
E=bridge/experiments/apple_view_icb
B="$LAB/results/apple-view-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-view-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --baseline-build "$OLD_BUILD" --baseline-direct "$OLD_DIRECT" --baseline-auto "$OLD_AUTO" --early-diagnostic "$EARLY" --diagnostic "$DIAGNOSTIC" --prefix-build "$PREFIX_BUILD" --prefix-runs "$PREFIX1" "$PREFIX2" --runs "$LAB/results/apple-view-direct-1-new" "$LAB/results/apple-view-auto-1-new" "$LAB/results/apple-view-direct-2-new" "$LAB/results/apple-view-auto-2-new" --out "$LAB/results/apple-view-audit-new.json"
```

The Apple metallib hash depends on the qualified local compiler. The Apple
source, its library and vendor drivers are not redistributed here.
