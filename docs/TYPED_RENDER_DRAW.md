# Typed AIR draws through the existing render-record path

The SDK-typed `metal::render_command.draw_primitives()` now has an opt-in AIR
translation to the existing render-state records. Original shader arithmetic,
branches, argument bindings and command order are preserved. The translated
shader uses NVIDIA's native compiler, then the owned public root encoder and
the existing materializer consume its records to produce checked images.

This is branch B progress on the existing driver, with no NAK producer import
or installed-driver change. It still requires an adapted application and the
project's certified state catalogue, not Apple's native ICB resource identity.

## Implemented contract

`air_render_draw_lowering.py` accepts the existing single command-buffer root
at buffer zero, literal triangle draw calls with scalar geometry/instance operands,
and reset calls. Other primitive kinds, indexed draws, resource/pipeline
setters, helper collisions and incompatible root layouts refuse. The shared
metadata graph decoder also serves the older reset-only translator; its two
qualified translations remain byte-identical.

The draw helper validates the live context header/capacity/alignment/index,
then writes a 64-byte nonindexed draw record. It preserves the preceding state
identity, replaces draw parameters and clears unused record fields. Reset
clears the whole record, including that identity. Later materialization checks
the certified state's bounds before any indirect draw. Unsupported geometry is
not submitted merely because a record contains a valid magic value.

The exact original shader profile contains dynamic vertex start/count,
instance count/base instance, conditional reset and reset-before/reset-after
modes. Its AIR SHA-256 is
`dc471f77f10b13a867f058062c2edd3d5a3446b176538e7ce7b5166da1e981b8`;
normalized IR SHA-256 is
`c7a2df83f3b1ae660a4c0b57e64b344c040d39597f937457c5a647ca57b8b764`.
Offline structural acceptance is distinct from execution qualification: the
builder pins that input, and GPU launch requires a native-code certificate
obtained by inspection first. Unknown profiles refuse.

The translated native program is 3,776 bytes, SHA-256
`8202bf60cd53893f26b1a3e09751c79bb2b037e471be16c8132ced54c81bd6f7`.
The corrected independent native MSL reference is 4,416 bytes, SHA-256
`ff73b41eff50fad1d7748b2255013dd2050bdb90f4dfa0f7ccd8e54fbe80b608`.
Inspection checks constructor restoration, unchanged code and absence of an
unresolved native CALL before execution. It is not itself execution evidence.

## Reception

The standalone producer reception uses three candidate/reference pairs plus
one missing-dispatch control. Each host covers 19 recipes: empty/single/full
dispatch, partial capacities, branches, tails, invalid headers/indices and
three ordering cases with identical ordinary inputs. Readbacks cover records,
arithmetic witnesses, input indices and guards; each live slot has one writer.

The seven final producer hosts pass **114 dispatches, 255,360 checked bytes and
1,836 exact uint32 arithmetic outputs**. Their records contain 492 draws and
174 resets, with 396 nonzero state identities preserved. All 171 complete
candidate/reference readback pairs and 228 repeat pairs match.

The render reception uses three repeats of nine modes:

- `draw_gpu`: translated typed producer and GPU record materialization.
- `draw_native`: the same producer, with independently encoded direct draws.
- `draw_reference`: an independent native MSL record producer and materializer.
- `draw_no_dispatch` / `draw_no_dispatch_native`: leave preceding records intact.
- `draw_after_reset` / native: reset before drawing, leaving no state identity.
- `draw_then_reset` / native: reset after drawing, leaving an empty command.

The frames include a complete six-vertex rectangle, repaired prior draw-kind
state, rejected start/count combinations, stale state identity and a missing
preceding producer. The candidate never reads GPU records/state choices on CPU
to decide which draw to encode. The direct reference uses the immutable input
recipe, rather than reading candidate results.

Public function argument encoders create each root; the library owns context
construction/resource declarations. Ordinary native PSOs are checked separately
against their program certificate. Scope/ICBs and argument encoders are released
before commit; completion retains roots/contexts. Native function getters are
restored before commit. [Root contract](RENDER_RECORD_ARGUMENTS.md).

The 27 final render hosts pass **216 frames / 2,654,208 float channels**, maximum
error zero, plus 168 typed-producer dispatches and 672 arithmetic witnesses.
All 216 ordinary native PSO programs match their certificate. The reception
checks 152,832 raster/materializer guard bytes, 110,592 root guard bytes,
144 reference/control image pairs, 144 repeat images and 4,272 repeat readbacks.
Against missing dispatch, frames 0/2/3/4/5 change by 30,831 float channels across
three repeats. Each reset-order control differs on frames 0/1/2/3, for 27,072
channels; the two order controls render identical images for distinct checked
record reasons (empty command versus absent state identity).

Two additional signed legacy render/root-contract hosts pass 196,608 channels
and 22 expected API refusals. The preceding reset producer rebuilds with an
identical executable and assets. All **307 CPU tests** pass from exported
sources. A complete seven-object public rebuild reproduces every runtime
object; its producer and render executables/assets match the GPU-tested builds
exactly, apart from an IR dump's ModuleID path. All **87 inventoried system
files** stay unchanged. No new compute IRv2 GPU cohort is claimed in this phase;
the core runtime remains byte-identical at the object level.

Exact counts, raw-result comparisons, regression/rebuild checks and system-file
hashes are in [validation](typed-render-draw-validation.json) and
[source chain](typed-render-draw-source-chain.json). Pilots and failed reference
qualification are excluded from final reception totals and retained separately.
The actual process inventory contains 47 terminal, nonoverlapping signed hosts:
34 final reception, two legacy regressions, six construction-only inspections,
three successful pilots and two earlier producer trials, one of which exposed
the reference failure below. That failed numerical verification is preserved
as an error, not reclassified as an expected negative control.

## Preserved reference failure

An initial MSL reference mixed `uint` record stores with a cast to an `ulong`
identity. Its compiled AIR already removed identity preservation before NVIDIA
compilation. The first reference execution terminated normally with intact
guards, but failed the numerical oracle: draw records lost eight identity bytes.
The translated candidate retained them correctly.

The reference now loads/stores both identity halves through the same `uint`
record representation. The CPU oracle was unchanged. Fresh compilation,
inspection, certificates and execution qualify that correction. This is a
reference-source correction; no NVIDIA compiler defect is inferred from that
mixed-type reference. Failed sources, AIR, outputs and terminal receipts remain
part of the local evidence.

## Reproduce

Use the [existing Xcode/Metal profile](AIR_RESET_DATAFLOW.md), local envytools,
fresh output directories and a single shared reservation:

```sh
python3 bridge/tools/public_air_render_draw.py build --out /absolute/new-producer
python3 bridge/tools/public_air_render_draw.py run \
  --build /absolute/new-producer --out /absolute/inspections/inspect-lowered \
  --variant lowered --mode inspect --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_render_draw.py certify \
  --run /absolute/inspections/inspect-lowered --envydis /absolute/envytools/envydis
python3 bridge/tools/public_air_render_draw.py run \
  --build /absolute/new-producer --out /absolute/new-execution \
  --variant lowered --mode execute \
  --certificate /absolute/inspections/inspect-lowered/certificate.json \
  --reservation-root /absolute/common-lab/bridge
```

Inspect/certify `reference` separately before running it. For rendering:

```sh
python3 tools/build_from_source.py --out build/fresh-runtime
python3 bridge/tools/public_render_state_catalogue.py build \
  --library build/fresh-runtime --out /absolute/new-render-build \
  --air-reset-build /absolute/new-producer \
  --air-reset-inspections /absolute/inspections \
  --render-argument-encoders --typed-render-draw
python3 bridge/tools/public_render_state_catalogue.py run \
  --build /absolute/new-render-build --out /absolute/new-render-execution \
  --mode draw_gpu --reservation-root /absolute/common-lab/bridge
```

Run all nine modes sequentially under `render-cohort/{0,1,2}/{mode}`. The combined
auditor expects producer builds under `build-03`, pairs under
`qualified-producer-cohort/{0,1,2}/{lowered,reference}` and a
`qualified-producer-no-dispatch` control; these names are only result layout.
Stop on any unresolved signed host or failed oracle, then inspect its exact
terminal receipt instead of replaying it.

```sh
python3 bridge/tools/audit_typed_render_draw.py /absolute/session \
  --render-build /absolute/new-render-build --out /absolute/new-audit.json
python3 -m unittest discover -s tests -v
python3 tools/check_publication.py
```

This bounded triangle/record contract is not general typed-command coverage,
Apple's ICB ABI, transparent ordinary-application integration, Metal 3/4
conformance or a performance benchmark. Indexed draw/resource/pipeline identity
mapping and additional native operations remain open. The runtime's seven
objects and installed system stack remain unchanged.
