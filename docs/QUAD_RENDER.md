# Combined indexed, vertex, pipeline and fragment rendering

An explicitly adapted Metal client uses one translated, SDK-typed producer to
select among eight CPU-certified combinations of two render pipelines, two
vertex buffers and two fragment argument buffers. It then emits two indexed
triangle commands, one with 16-bit and one with 32-bit indices. A GPU
materializer selects from sixteen pre-encoded native draw candidates. The
fragment arguments contain a genuine Metal texture, sampler and nested parameter
buffer. Changing each of the three selectors changes the resulting image.

The application registers the exact producer library and native visual profile.
It uses `newPipelineRenderCommandFunctionWithLibraryData:` for the two-word
argument encoder and
`newIndexedVertexPipelineFragmentRenderCommandArgumentContextWithCommands:`
for the four-table context. The source command order and dataflow are preserved
by the bounded AIR lowering. It is compiled by the existing NVIDIA backend;
NAK is not substituted. The encoder retains the certified resources and
declares indirect usage through the same command buffer. Context and resource
contents must remain unchanged until completion.

The CPU planner builds index, vertex, pipeline and fragment rows only from
retained certified objects and the source catalogue. Its 16 index rows are
followed by 48 vertex, 32 pipeline and 32 fragment transition rows. A shader
walks and checks the relevant owned headers in order before selecting a state.
This is a pinned project ABI, not Apple's native ICB identity or a sandbox for
arbitrary pointers. The test does not change the installed driver or make
unmodified applications compatible.

The CPU oracle verifies each context and table against independently derived
rows, guarded records, argument buffers, texture input and the complete image.
Direct native draws provide separate pixel references. Cases exercise all eight
selector combinations, pipeline-first and draw-before-setters order, reverse
selection, absent dispatch, reset, foreign vertex/fragment/index pointers,
invalid headers and root/resource contract refusals. Both index formats use
certified spans. The two pipeline variants use smooth and flat interpolation;
the fragment buffer changes the scaling of texels read from the texture.

On October 27, 2026, an independent audit rechecked 49 combined-render hosts
and six same-runtime regression hosts, all serialized. It checked 602,112 image
channels and 602,112 input-texture channels; maximum CPU error was 7.95e-8.
Twenty native image pairs and eight repeated image pairs matched byte for byte,
and the eight selector combinations produced distinct images. All 366 CPU tests
passed both locally and in a source export. The export rebuilt the tested
producer and client byte-identically and passed two further serialized GTX hosts.
[Audit and fingerprints](quad-render-validation.json).

## Reproduction

Use the supported macOS/SDK/driver profile, fresh output directories and a
shared GPU reservation. Submit only one Metal host at a time. Build and inspect
the exact quad producer as described in [EIGHT_STATE_CATALOGUE.md](EIGHT_STATE_CATALOGUE.md).
Inspection creates a pipeline but does not execute the producer.

```sh
python3 tools/build_from_source.py --out build/quad-runtime
python3 bridge/tools/public_quad_render_probe.py build \
  --library "$PWD/build/quad-runtime" --producer /absolute/quad-producer \
  --inspection /absolute/quad-inspection --out /absolute/client-build
python3 bridge/tools/public_quad_render_probe.py run --build /absolute/client-build \
  --out /absolute/results/final-gpu7 --mode gpu7 \
  --reservation-root /absolute/common-lab/bridge
```

The complete mode list, repeat cases and same-runtime regression inputs are in
`bridge/tools/audit_quad_render.py`. Recheck a complete results directory with
`audit_quad_render.py ROOT --out /absolute/audit.json`. Each host has a frozen
oracle and terminal reservation receipt. This is bounded adapted-client
support; it does not establish general Metal 3/4 support, transparent app
integration or a performance gain.
