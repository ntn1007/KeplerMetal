# GPU selection among certified render states

The render adapter now lets a native GPU producer select among certified
pipeline/resource states for each logical draw. This extends the preceding
[scalar draw-record route](GPU_RENDER_COMMAND_RECORDS.md). Selection requires
no CPU readback of the GPU record, execution range or selected identity.

The execution mechanism is explicit: **the CPU encodes all certified candidate
states; GPU-produced indirect arguments enable the selected candidate and
suppress the others**. This is a bounded implementation of selection semantics,
not GPU emission of arbitrary native pipeline-setting packets. CPU encoding
cost grows with the candidate count; no performance improvement is claimed.

This is branch B and application integration level 2. Native shaders, queues,
resources and indirect draws remain provided by the existing NVIDIA driver.
No driver, framework, OCLP, firmware, protection or WindowServer change occurs.

## Catalogue and record contract

`newRenderStateCatalogueWithCommands:alternatives:error:` snapshots the execution
ICB and distinct alternative ICBs belonging to the same scope. They must have
equal logical capacity. The immutable catalogue exposes a logical command count
and a process-local opaque identity for each candidate ICB row. An identity
names that row's pipeline/resources **at the requested logical slot**; it is
neither a native Apple pipeline resource ID nor a globally portable PSO ID.

Every command is certified through the existing native render transport before
catalogue creation succeeds. The catalogue keeps native records/resources but
only weak references to the source software ICBs and scope. Source ICBs must
remain alive and unchanged through preparation and consumption. Resetting or
mutating an alternative invalidates the snapshot just as mutating the execution
ICB does. An ordinary CPU ICB copy does not copy a prepared execution plan.

Up to four candidates are accepted, with logical slots times candidates limited
to the existing 16-entry native sequence capacity. Expansion is logical-slot
major, then candidate: this preserves draw order when different logical slots
select different states. Empty slots stay empty. All candidates are validated
even when their GPU predicate will suppress their draw.

The new [`KeplerRenderStateRecords.h`](../bridge/src/KeplerRenderStateRecords.h)
defines separate 64-byte records/templates, preserving the earlier 32-byte ABI.
A record contains magic, kind, five native argument words, an opaque 64-bit
identity and zero reserved fields. There are no resource pointers or command
stream addresses in the GPU record. The host seals a template for every
logical-slot/candidate pair, including identity, kind, geometry bounds and
base vertex/instance. The exact native materializer is pinned to:

```
c72292b98ea9811bf131797514fb2e97d053d7598976e075c06b5ecdebc2cf47
```

Registration checks the immutable library digest and complete six-buffer
reflection contract. The GPU recognizes identities only from the prepared
catalogue, checks reserved fields, kind and the certified geometry envelope,
and produces zero native draw arguments for invalid records. Witness reasons
are 0 selected/valid, 1 magic/reserved mismatch, 2 kind mismatch, 3 geometry/base
bounds, 4 empty slot, 5 unknown catalogue identity, and 6 unselected candidate.
An identity from another catalogue therefore cannot silently select a current
state. IDs are unique across scopes/catalogues within this process, not across
process launches; they are not native hardware capabilities.

## Use

1. Install the existing render scope and register certified native pipelines
   and argument-buffer/resource profiles. Encode the maximum geometry envelope
   in each CPU ICB state.
2. Register the state materializer with
   `enableGPURenderStateCatalogueWithLibraryData:expectedSHA256:error:`.
3. Create the catalogue. Upload its public identities as producer input and
   encode the GPU record/range producer on a retained scope command buffer.
4. Before opening the render pass, call:

```objc
[scope prepareIndirectRenderCommands:executionICB
                     stateCatalogue:catalogue
                     commandRecords:gpuRecords
               commandRecordsOffset:recordOffset
                     indirectBuffer:gpuRange
               indirectBufferOffset:rangeOffset
                      commandBuffer:commandBuffer
                              error:&error];
```

5. Open the scoped render encoder on that same command buffer and consume
   `executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:` once.

Range offsets require four-byte alignment; state-record offsets require eight.
Producer/resource synchronization, immutable snapshots, successful completion
before re-preparation and discard after partial encoding failure remain the
existing contract. The scope restores the caller pipeline and touched vertex/
fragment bindings, including inline bytes. The CPU never resolves the GPU's
chosen identity on the candidate path.

## GTX evidence

The client uses four logical slots, two candidate ICBs and six occupied native
draws after expansion. It combines direct, UInt16 and UInt32 indexed triangles,
positive/negative base vertices, nonzero base instances, private textures and
fragment tables, nested private parameter buffers and two sampler policies.

Three native-reference pairs separate the effects: full pipeline/resource
selection, different pipelines with identical resources, and different
resources with identical pipelines. Fixed-candidate controls demonstrate that
both choices affect the result. Invalid/foreign identities, wrong kind,
out-of-range arguments and reserved fields are suppressed. Separate absent
producer/consumer controls preserve only the following caller marker.

The twelve-mode new cohort checks 1,093,632 float channels with zero observed
error and 68,448 raster/argument/witness guard bytes. All input buffers,
templates and sampled textures are checked in full. The independent CPU oracle
checks shading, sampling, clipping and triangle coverage. Exact process/raw
comparison counts are in the [validation summary](gpu-render-state-validation.json).

All frames drain the encoding call's autorelease pool, observe scope/ICB
destruction and sampler liveness, then commit the retained native command
buffer. Native direct references explicitly retain indirect resources until
completion; candidate executions use the runtime's owned snapshots/leases.
The separate `release` mode is one nonempty frame. The `contracts` mode checks
14 refusal cases on each of two frames, including alternative mutation,
snapshot restoration and double consumption.

An initial pilot omitted the explicit zero clear color and failed the oracle
on background alpha. Its raw evidence is preserved; alpha-one diagnostics
explained every difference. The final client explicitly clears RGBA to zero.
This was a test-recipe correction, not a GPU kernel or driver fix.

The GPU-tested complete archive is:

```
796d6703bdee6b0697492cab7b7c1a5586b21d757813c389c416ce0edc68ad68
```

Only the ICB runtime object changes from `ed87b2bd…`; the other six objects stay
byte-identical. There are 51 runtime source files, and both preceding native
materializer pins remain unchanged. Source exports contain no compiled shader,
driver or binary archive. Rebuild comparison separates object/member payloads
from `ar` timestamp/group-ID metadata. The exact driver profile and SDK remain
those recorded in [DRIVER_PROFILES.md](DRIVER_PROFILES.md).

## Reproduction

Use fresh directories and the existing common host reservation. Every Metal
host, including construction controls, uses an immutable signed executable and
must reach a verified terminal state before another host runs.

```sh
python3 tools/build_from_source.py --out build/render-states-local
python3 bridge/tools/public_render_state_catalogue.py build \
  --library build/render-states-local --out "$KP_WORK/client"
python3 bridge/tools/public_render_state_catalogue.py run \
  --build "$KP_WORK/client" --out "$KP_WORK/gpu" --mode gpu \
  --reservation-root "$KP_LAB"
```

Also run `native`, `pipeline_only`, `pipeline_only_native`, `resources_only`,
`resources_only_native`, `forced_0`, `forced_1`, `no_producer`, `no_consumer`,
`release`, `contracts` serially. Stop at failure and inspect that exact process
and lease. The runner validates readbacks in a fresh isolated Python interpreter
using the frozen oracle/helper copies; mutable modules in the source launcher
cannot replace the already-built oracle. That verifier invocation and status
are recorded separately from native execution.

`audit_render_state_catalogue.py --help` gives the complete reception auditor,
including the preceding 42-process draw-record/compute/adapter regression on the
same new archive. Portable falsification tests call no GPU API:

```sh
python3 -m unittest discover -s tests -p test_render_state_catalogue.py -v
```

## Remaining scope

This is certified candidate selection through native indirect-draw predicates.
It does not implement native Apple ICB layout, native MSL `render_command`,
GPU submission of arbitrary pipeline/resource packets or transparent system
integration. The tested profiles use two candidates and four slots; other
capacities, catalogue reuse, concurrent mutation, untracked synchronization,
draw-index/query-counter equivalence and GPU-error recovery remain unqualified.
No benchmark or general Metal 3/4 conformance is claimed. A source-level render
command interface and a real application reception are next integration steps;
the complete modernized-driver objective remains open.
