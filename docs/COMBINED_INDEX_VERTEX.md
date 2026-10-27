# Combined typed indexed draws and vertex-buffer transitions

This scoped project path combines a typed `render_command.set_vertex_buffer`
with `draw_indexed_primitives` in one shader. It uses the installed NVIDIA
compiler, driver and a retained project context. The tested shader handles two
logical slots using 16-bit and 32-bit device index pointers and preserves the
source operation order. It is an explicit adapted-client extension, not native
Apple ICB identity, transparent application support or a system-driver update.

## Dual context and bounds

`newIndexedVertexRenderCommandArgumentContextWithCommands:stateCatalogue:
commandRecords:commandRecordsOffset:commandBuffer:error:` derives two sealed
tables from the same live, prepared catalogue. The original 32-byte root prefix
and the version-one `KPIX` header and 48-byte index rows retain their existing
layout. Immediately after those rows, a version-one `KPVX` header precedes the
32-byte vertex-transition rows. Both GPU pointers are derived by the runtime;
the application does not construct them. The runtime retains/declares the
relevant vertex, index and fragment buffers and refuses record/root aliases.

The combined vertex helper validates the index header before locating and
validating the secondary vertex header; it compares the supplied vertex pointer
without dereferencing it. The indexed helper keeps its existing bounds/format
checks. An invalid or missing table causes a fail-closed inactive record in
this bounded project contract; this is not a sandbox for arbitrary GPU pointers.
The indexed prefix keeps its previous layout; running the old indexed producer
against the dual context has not been separately GPU-qualified. The older
standalone vertex producer expects KPVX at the first extension and is not
interchangeable with the combined producer.

The planner admits a vertex transition only between fully certified states that
match in pipeline, index buffer/offset/format, geometry, fragment bindings and
all other vertex bindings. Application code must keep the roots and underlying
resources immutable through completion. This mechanism does not implement
arbitrary state creation, null/unbinding, dynamic stride, constant-address-space
buffers, arbitrary shader libraries, Apple ICB resource IDs, or general Metal
3/4 conformance.

## Verification and limits

The signed test client creates two command slots and two complete states. It
uses separate real index buffers (UInt16 and UInt32), renders two nonoverlapping
halves, compares GPU readbacks to a CPU oracle and compares full images to a
direct native Metal reference. Controls cover no producer dispatch, a disabled
setter, drawing before the setter, reset after drawing, foreign vertex/index
buffers, missing vertex/index extensions and reverse state selection. All
processes use the shared GPU reservation and an immutable signed executable.
The test retains client owners through completion; early-release lifetime,
nonempty fragment bindings, mixed indexed/nonindexed slots, combined-context
alias refusals, arbitrary geometry and larger catalogues remain unqualified.

On October 27, 2026, 40 signed terminal processes checked 491,520 float
channels with maximum error zero. The two series included 36 producer
dispatches, 144 checked index rows and 432 checked vertex-transition rows.
Twenty native image pairs and 20 repeated image pairs matched exactly. The
no-dispatch, disabled and reverse controls each differ from the active result
in 6,144 channels; missing/foreign resources and reset differ in 12,288.
These are correctness and causal controls, not a performance benchmark.

[Exact test counts and evidence](combined-index-vertex-validation.json) and
[source chain](combined-index-vertex-source-chain.json) are separate from any
performance claim. One initial offline IR compile failed because two local
names collided; that error was fixed before a GPU process was launched. No new
performance benchmark or hardware-video qualification is claimed.

On the same runtime, 19 signed non-regression hosts rechecked indexed and
vertex roots plus compute paths: 466,944 float channels and 2,291,712 exact
uint32 results. Both the checkout and a fresh public source export passed 345
CPU tests. The exported source rebuilt the same 58 runtime sources, seven
objects, eight static-archive members and producer/client executables; archive
container metadata differs. The 87 inventoried system files were unchanged.
These checks do not requalify every existing subsystem.

## Reproduction

Use the qualified Xcode/Metal SDK and installed driver; select fresh output
paths and the common reservation root. The build phases perform no GPU work.

```sh
python3 tools/build_from_source.py --out build/combined-runtime
python3 bridge/tools/public_air_combined_index_vertex.py build --out /absolute/producer
python3 bridge/tools/public_air_combined_index_vertex.py inspect \
  --build /absolute/producer --out /absolute/inspection \
  --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_combined_index_vertex.py certify \
  --run /absolute/inspection --envydis /absolute/envytools/envydis
python3 bridge/tools/public_combined_index_vertex_probe.py build \
  --library build/combined-runtime --producer /absolute/producer \
  --inspection /absolute/inspection --out /absolute/render-client
python3 bridge/tools/public_combined_index_vertex_probe.py run \
  --build /absolute/render-client --out /absolute/cohort/0/gpu --mode gpu \
  --reservation-root /absolute/common-lab/bridge
```

Create parents first. Run every mode from `verify_combined_index_vertex.py`
sequentially under `cohort/{0,1}/{mode}`; never rerun a pending or unknown
process without checking its exact receipt. Reaudit the results offline:

```sh
python3 bridge/tools/audit_combined_index_vertex.py /absolute/cohort \
  --build /absolute/render-client --out /absolute/combined-audit.json
python3 -m unittest discover -s tests -v
python3 tools/check_publication.py
```

The complete goal of hardware support remains open. Other primitives, indexed
formats and offsets, application integration, resource lifetimes and remaining
hardware engines need their own evidence; a single successful scene is not a
feature-family certification.
