# Runtime-owned typed pipeline transitions

The explicitly adapted render path now derives its pipeline-transition table
from an existing certified render-state catalogue. The runtime retains the
pipeline objects and the index, vertex and fragment buffers used to construct
the table. Only states whose slot, draw arguments and resource bindings match
may differ in pipeline. Duplicate or ambiguous mappings and excessive tables
are refused. The runtime creates unique process-local tokens; these values are
not Apple `MTLResourceID`s and are not a native Apple ICB implementation.

The pipeline-specific context uses a two-word, aligned Shared argument root.
The scoped argument encoder accepts the context's ICB at index 0 and a retained
catalogue pipeline at index 1, in either order. It constructs both words itself.
A foreign pipeline, wrong index, incomplete root, overlapping root and aliases
with retained buffers are rejected. Immediately before the producer is encoded,
the runtime checks that the root is still intact, that its catalogue and
command buffer are current, and that use occurs on the creating thread. It
declares the indirect resources and keeps the context and owners through the
command buffer's completion. The caller must not change the root or associated
resources while work is pending; these checks do not sandbox arbitrary GPU
addresses or detect a subsequent external write.

On October 27, 2026, two integrated cohorts used 18 signed hosts and checked
221,184 float channels against the CPU. Eight native-image pairs and nine
repeat-image pairs matched byte for byte; maximum CPU error was 5.97e-8.
Two further hosts exercised native reflection and the contract case, including
releasing the caller's local root and pipeline references after scope restore.
Other catalogue/context owners remained alive during that bounded test.

On the same runtime, ten older vertex and combined indexed/vertex hosts checked
122,880 float channels; three compute regression hosts checked 460,800 exact
uint32 results in their dataflow cases and a pointer-contract case. Across the
33 independently audited hosts, 24 expected API refusals were observed. These
results do not qualify unrelated render profiles, concurrent contexts, all
resource lifetime arrangements or performance.
[Recorded audit and exact build fingerprints](pipeline-runtime-validation.json).
An independent source export passed 351 CPU tests and rebuilt a client
byte-identical to the reflection/lifetime client. Two additional signed GTX
hosts from that export passed the active and contract cases and matched the
native direct-draw image. The static archive container itself had a different
hash; only the linked executable was byte-identical.

The function's native reflection describes the lowered 16-byte struct. Only
explicitly registered function instances receive the project's argument
encoder; the installed compiler, system driver and native pipeline factory are
unchanged. The path is an opt-in process-local adapter, not transparent support
for arbitrary existing applications or a claim of Metal 3/4 conformance.

## Adapted application sequence

After installing the existing rendering scope, registering its render profiles
and enabling the render-state materializer, create a catalogue whose states
retain the real pipeline and bindings. Register the pinned lowered shader and
create its native compute pipeline. Create a pipeline context on the same
uncommitted retained-reference command buffer. The essential argument calls are:

```objc
id<MTLFunction> function = [scope newPipelineRenderCommandFunctionWithLibraryData:producer
    expectedSHA256:producerSHA functionName:@"probe_boundary" rootBufferIndex:0 error:&error];
KPRenderCommandArgumentContext *context =
    [scope newPipelineRenderCommandArgumentContextWithCommands:commands
        stateCatalogue:catalogue commandRecords:records commandRecordsOffset:offset
        commandBuffer:commandBuffer error:&error];
id<MTLArgumentEncoder> arguments = [function newArgumentEncoderWithBufferIndex:0];
[arguments setArgumentBuffer:sharedRoot offset:rootOffset];
[arguments setIndirectCommandBuffer:commands atIndex:0];
[arguments setRenderPipelineState:cataloguePipeline atIndex:1];
// Set the certified compute pipeline on computeEncoder before preparation.
BOOL ready = [scope prepareRenderCommandArgumentContext:context argumentBuffer:sharedRoot
    offset:rootOffset computeEncoder:computeEncoder commandBuffer:commandBuffer error:&error];
```

The caller must check every creation, error and `ready` before dispatch; use
only the qualified translated program and certified native code. Then use the
existing render-state materializer and indirect-render preparation in the same
command buffer. The caller may restore the scope after encoding, as in the
qualified client. The standalone context remains available; the separate
[combined context](TRIPLE_RENDER.md) also includes indexed and vertex transitions.

## Reproduction

Rebuild the source runtime under its checkout's `build/`, and build and inspect
the exact producer as described in [the preceding experiment](TYPED_PIPELINE_RENDER.md).
Use fresh output directories, the same driver profile, and the shared GPU
reservation; do not overlap hosts or retry a still-running process.

```sh
python3 tools/build_from_source.py --out build/pipeline-runtime
python3 bridge/tools/public_pipeline_binding_integrated.py build \
  --library "$PWD/build/pipeline-runtime" --producer /absolute/producer \
  --inspection /absolute/inspection --out /absolute/client-build
python3 bridge/tools/public_pipeline_binding_integrated.py run \
  --build /absolute/client-build --out /absolute/results/integrated-gpu-01 \
  --mode gpu --reservation-root /absolute/common-lab/bridge
```

The integrated modes are `gpu`, `native`, `no_dispatch`, `no_dispatch_native`,
`reverse`, `reverse_native`, `reverse_no_dispatch`, `reverse_no_dispatch_native`
and `contracts`. Run them serially in two cohorts, using the names consumed by
`audit_pipeline_runtime.py`. Its same-runtime regression inputs use the existing
vertex and combined-index/vertex builders. The independent verifier checks raw
context and root bytes, tokens and transition rows, the native program
certificate, CPU pixels and native direct-draw comparisons.
