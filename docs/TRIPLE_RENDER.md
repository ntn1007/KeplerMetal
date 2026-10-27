# Combined pipeline, vertex and indexed render commands

An explicitly adapted Metal client combines pipeline selection, a vertex-buffer
transition and 16/32-bit indexed triangle draws in one typed producer. It uses
the existing runtime-owned argument root, retained resources and certified
render-state catalogue. The client does not construct GPU addresses or
pipeline tokens. This is an opt-in process-local adapter, not a replacement
system driver or native Apple ICB ABI.

The context keeps the previous 32-byte record header, followed by bounded
`KPIX` index rows, `KPVX` vertex-transition rows and `KPPP` pipeline-transition
rows. Existing single- and two-extension layouts remain unchanged. The pipeline
helper validates both preceding headers before locating the third table; the
index and vertex helpers keep their existing prefixes. Contexts and resources
are retained by the runtime through the command buffer's completion. The
client must preserve root and resource contents while GPU work is pending.
The bounds and identities are a project contract, not a sandbox for arbitrary
GPU addresses.

The catalogue has four states per logical slot: two pipelines crossed with
two vertex bindings. The CPU planners require all other bindings and draw
properties to match for each transition. The producer tests both setter orders,
drawing before setters, reset, missing dispatch, foreign vertex/index buffers,
and each selector independently. One slot draws 16-bit indices and the other
32-bit indices. The two pipelines use smooth and flat interpolation, while
nonuniform vertex colours make the four selector combinations distinguishable.
The existing catalogue is limited to four source states and 16 total
state/slot combinations; the index table is limited to 16 rows and each
transition table to 64 rows. Missing intermediate catalogue states cannot
silently select a different state and are rejected by the transition helpers.
An adapted application uses `newPipelineRenderCommandFunctionWithLibraryData:`
for the pinned lowered function and
`newIndexedVertexPipelineRenderCommandArgumentContextWithCommands:` for the
combined context. The two-word argument encoder and preparation sequence are
the same as in [the pipeline-only contract](PIPELINE_RUNTIME_INTEGRATION.md).

The independent CPU oracle checks each smooth pixel analytically and checks
that flat pixels are constant within each triangle and are input vertex colours.
Complete images are also compared byte for byte with separate native direct
draws. The per-run oracle checks the full guarded root, context, record,
indices, vertices and witness; it reconstructs expected vertex and pipeline
tables from the runtime's observed object identities. Unsupported operations,
unknown AIR layouts and changed metadata are rejected before translation.

Before GPU dispatch, a separate signed construction-only host captures the
exact native NVIDIA program. The executable checks the driver, library and
native program certificate. An offline disassembly rejects unresolved calls.
This is a bounded pinned program; neither successful construction nor the
specific tested scene establishes general Metal 3/4 support or a speedup.

One preliminary `pipeline_only` run completed on the GPU but its frozen oracle
failed because a local function name shadowed a selector flag. The raw result
was retained and passed an independently invoked corrected oracle; the final
cohort uses a rebuilt, frozen oracle with a regression test for the selector
choices. A separate attempted launch was refused before GPU use because its
output directory already existed. Neither event is counted as a final pass.

On October 27, 2026, the final audit rechecked 58 signed, serialized hosts on
the same runtime: 42 combined-render cases, six malformed-header controls,
eight older render-path regressions and two compute regressions. The combined
cases checked 516,096 float channels, 336 index rows, 1,008 vertex rows and
672 pipeline rows. The maximum difference from the CPU oracle was 7.95e-8.
Twenty-three native image pairs and 21 repeated image pairs matched exactly;
the four independent selector combinations produced distinct images. Two
contract cases observed 16 expected API refusals. Both compute regressions
checked 460,800 exact uint32 results. [Audit and fingerprints](triple-render-validation.json).

The two setter orders and draw-before-setter case produced the same final
image in this profile. Invalid index, vertex or pipeline header controls
produced the same empty image as their native references. This does not prove
correctness for arbitrary corrupted allocations or missing catalogue states.
The corrected preliminary host and the later host with additional controls
were separate frozen binaries; each result was checked against its own frozen
oracle. An independent source export passed 356 CPU tests and rebuilt the
producer and the later client byte-identically. Two further GTX hosts from
that export passed the active and contract cases and matched the native image.

## Reproduction

Use the supported macOS/SDK/driver profile, a fresh output directory and the
existing shared GPU reservation. Run one Metal host at a time. Build from this
source checkout; `envydis` is a separately obtained dependency.

```sh
python3 tools/build_from_source.py --out build/triple-runtime
python3 bridge/tools/public_air_triple_render.py build --out /absolute/producer
python3 bridge/tools/public_air_triple_render.py inspect --build /absolute/producer \
  --out /absolute/inspection --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_triple_render.py certify --run /absolute/inspection \
  --envydis /absolute/envytools/envydis
python3 bridge/tools/public_triple_render_probe.py build \
  --library "$PWD/build/triple-runtime" --producer /absolute/producer \
  --inspection /absolute/inspection --out /absolute/client-build
python3 bridge/tools/public_triple_render_probe.py run --build /absolute/client-build \
  --out /absolute/results/final-gpu-01 --mode gpu \
  --reservation-root /absolute/common-lab/bridge
```

The audited modes and cohort naming are in `audit_triple_render.py`. Its
same-runtime regression inputs use the existing pipeline and combined
index/vertex builders. Run all cases with fresh directories, then use
`audit_triple_render.py ROOT --out /absolute/audit.json`. The audit replays the
frozen oracles, checks serialized receipts, compares native/repeat images and
requires all four selector combinations to differ.

The runtime still requires an adapted application and explicitly registered
profiles. Pipeline+vertex+index is only one combination. A later fragment-resource
combination is documented in [QUAD_RENDER.md](QUAD_RENDER.md); broader
resource mutation and application integration remain separate work.
