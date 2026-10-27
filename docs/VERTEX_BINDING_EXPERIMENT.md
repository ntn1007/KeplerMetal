# Scoped typed vertex-buffer state transitions

An explicitly adapted application can now use the tested typed MSL
`render_command.set_vertex_buffer(device T*, index)` path with the existing
NVIDIA compiler and driver. The producer switches between two previously
certified render states, and the existing GPU materializer selects the matching
native indirect draw. No Apple ICB identity is fabricated and no system driver
or framework is replaced.

This is a bounded laboratory implementation, not general Metal ICB support.
The source shader and AIR profile are pinned; arbitrary shader translation,
null/unbinding, dynamic stride, constant-address-space pointers and setters on
an empty/reset state are not implemented. The current vertex and indexed root
extensions cannot be combined. The tested application uses the project scope,
context and argument encoder explicitly; transparent applications remain open.

## Owned state-transition context

`newVertexRenderCommandArgumentContextWithCommands:stateCatalogue:
commandRecords:commandRecordsOffset:commandBuffer:error:` revalidates the live
catalogue and uses its prepared record snapshots to construct an immutable
Private context. It preserves the existing 32-byte root prefix and adds a
`KPVX` extension and up to 64 inline 32-byte rows. A row contains the source
and destination project identities, the exact destination buffer GPU address,
the logical command slot and the binding index. These identities are not Apple
GPU resource IDs.

The C++ planner accepts a transition only when pipeline, index binding, draw
envelope, fragment bindings and every other vertex binding match. It refuses
ambiguous address aliases, duplicate state/slot identities, invalid bounds and
an oversized table. The host derives addresses from live Metal objects, retains
and declares catalogue buffers, rejects overlaps with command records, and
rejects a Shared argument root that overlaps the retained buffers. The shader
compares but never dereferences the supplied vertex pointer; an unmatched
transition clears the record in this conservative project contract. This is not
a sandbox for arbitrary pointers or a complete implementation of native Metal
setter semantics. Context/root/resources must remain immutable and alive until
command-buffer completion.

The test deliberately keeps the client owners alive through completion; it does
not independently qualify early owner release, nonempty fragment/index buffer
alias refusals, GPU-selected initial states, multi-slot transitions or every
catalogue combination. A transition is restricted to complete certified states,
so callers must provide the reachable combinations in advance.

## Evidence

On 27 October 2026, 26 signed terminal processes ran sequentially on the GTX
880M. Two series covered both transition directions, native direct-draw
references, no-dispatch controls, a disabled setter, a separately allocated
foreign buffer and two alias refusals per series. An independent CPU oracle
checked **319,488 float channels with maximum error zero**, 156 transition rows,
18 producer dispatches and the guards/records/root/context in each process.
Twelve candidate/native image pairs and 13 repeat pairs matched exactly.
Compared with the corresponding no-dispatch and disabled controls, the setter
changed 6,144 image channels per trial; the foreign-buffer control changed
12,288. These comparisons show the change in the tested scene, not a benchmark.

The 32-bit and 64-bit root/table fields are checked before submission, and the
runtime never writes instructions into the native program. The captured native
program was inspected before execution: its 2,432 bytes have SHA-256
`f8cc2d2f68617cc21590f13eb316923501772b1182e423a13db2fe879ee051eb`;
no unresolved CALL was found. Construction alone is not execution evidence:
the completed command buffers, CPU-checked GPU readbacks and image controls
provide that evidence for this restricted shader.

The first exploratory host omitted redundant device-name fields required by
its verifier; an offline recheck derived them from its recorded device identity
without changing the frozen receipt. The final cohort uses a corrected client.
An initial full CPU run also failed its publication manifest because the two
changed source hashes had not yet been updated; the manifest was corrected and
the full 337-test CPU suite passed. Frozen source correspondence is documented
in [the source chain](vertex-binding-source-chain.json) and [validation summary](vertex-binding-validation.json).

On the same new runtime, four signed indexed-render regression hosts checked
32 frames / 393,216 float channels, and nine compute hosts checked 2,291,712
exact uint32 results. A fresh public source export passed all 337 CPU tests.
Its 58 runtime sources, seven object files, eight static-archive members and
both producer/client executables match the builds used in qualification;
archive container metadata differs. The 87 inventoried system files were
unchanged. These checks do not requalify every earlier subsystem.

## Reproduction

The existing public build requires the qualified Xcode/Metal profile, an
unmodified driver and the same shared host reservation for all Metal hosts.
Use fresh directories on every build and run. No source build dispatches GPU
work.

```sh
python3 tools/build_from_source.py --out build/vertex-runtime
python3 bridge/tools/public_air_vertex_binding.py build --out /absolute/producer
python3 bridge/tools/public_air_vertex_binding.py inspect \
  --build /absolute/producer --out /absolute/inspection \
  --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_vertex_binding.py certify \
  --run /absolute/inspection --envydis /absolute/envytools/envydis
python3 bridge/tools/public_vertex_binding_probe.py build \
  --library build/vertex-runtime --producer /absolute/producer \
  --inspection /absolute/inspection --out /absolute/render-client
python3 bridge/tools/public_vertex_binding_probe.py run \
  --build /absolute/render-client --out /absolute/cohort/0/gpu --mode gpu \
  --reservation-root /absolute/common-lab/bridge
```

Create parent directories beforehand. Run the modes in
`verify_vertex_binding_render.py` sequentially under `cohort/{0,1}/{mode}`;
include `EXTRA_MODES` as well as `MODES`. The offline auditor rechecks the
frozen oracles, reservations, images and controls:

```sh
python3 bridge/tools/audit_vertex_binding_probe.py /absolute/cohort \
  --build /absolute/render-client --out /absolute/vertex-audit.json
python3 -m unittest discover -s tests -v
python3 tools/check_publication.py
```

The current work makes no claim of Metal 3/4 conformance, an installed driver
upgrade, full GTX 880M support, hardware-video support or a performance gain.
