# Native source interface for certified render commands

`bridge/src/KeplerNativeRenderCommands.h` adds an opt-in MSL interface over the
existing 64-byte certified render-state records. NVIDIA's native Metal compiler
compiles the producer; neither NAK nor instruction import is involved in this
producer. The existing catalogue materializer and seven-object runtime are unchanged.
This is branch B, application integration level 2.

The explicit `keplermetal::` namespace avoids confusion with Apple's opaque
`metal::render_command`. No SDK header, Apple type, driver or framework is replaced.
Existing applications need source adaptations; this is not native Apple ICB ABI
support or transparent integration.

## Source contract

```cpp
#include "KeplerNativeRenderCommands.h"
// records: host-owned device allocation, capacity: validated logical slot count.
keplermetal::render_command_buffer commands{records, capacity};
keplermetal::render_command command(commands, slot);
command.reset();
command.set_render_state(catalogueIdentities[choice]);
command.draw_primitives(vertexStart, vertexCount);
```

`draw_indexed_primitives(index_type, firstIndex, indexCount, instanceCount,
baseVertex, baseInstance)` supports UInt16 and UInt32 index bindings. First index
is an element offset in the host-sealed index binding. Only host-certified
triangle profiles are supported. Pipeline and resource choices remain bundled
in a catalogue identity for the destination logical slot; no arbitrary GPU
pipeline/resource packet or raw PSO handle is introduced.

A slot must be initialized with `reset()` before first use. Draw calls replace
its geometry and clear reserved fields while preserving its state identity.
`set_render_state` may update a record but does not authorize the supplied token.
The existing GPU materializer independently validates identity, geometry and
reserved fields against the immutable host catalogue.

`copy_command(source)` snapshots a completed command in the same records
allocation and capacity. Self-copy is supported. Invalid source indices,
capacity mismatches and incomplete sources clear a valid destination and return
false. Unsupported index types likewise clear the destination. Out-of-range,
null or invalid-capacity destinations return false without writing. Capacity is
bounded at 16; the caller must supply the actual valid allocation, not an
arbitrary GPU pointer. Boolean success means a representable write, not that
its state/geometry will pass the materializer.

One invocation owns each writable slot. Copying needs a completed source writer;
these operations implement no cross-invocation memory barrier or synchronization.
Host ownership, queue ordering, private resource lifetimes and catalogue snapshot
rules remain those of [the existing catalogue](GPU_RENDER_STATE_CATALOGUE.md).

## GTX reception

The source producer builds each command in a staging slot, self-copies it,
copies it to its destination, then resets the staging slot. It covers direct,
UInt16 and UInt32 indexed geometry, negative base vertices, nonzero base
instances, two state candidates and four logical slots. Bounds/null/capacity,
failed-copy clearing and unsupported-index clearing are checked by the producer;
the independent CPU oracle checks its completion witness and all final records.
No intentionally malformed native command stream is submitted.

The same application host and independent raster oracle used in the raw-record
reference remain unchanged. The twelve-mode reception checks **1,093,632 new
float channels**, maximum error zero, **68,448 guard bytes**, and **33 exact
native-reference image pairs**. All output files are compared with their matching
raw-record reference; the source producer metallib is required to differ while
the runtime and materializer remain identical. Exact hashes and pair counts are
in [the validation summary](native-render-source-validation.json).

Pipeline-only, resource-only, forced-candidate, missing producer/consumer,
nonempty drained-pool release and 28 existing API-refusal controls are retained.
The 199 portable CPU tests also pass. The preceding 54-process runtime reception
is historical evidence for the unchanged archive, not 54 new executions here.

An initial CPU-only build exposed ambiguous unqualified `render_command` lookup
between the project and SDK namespaces. The corrected producer explicitly
qualifies the project class; that failed build is not GPU execution evidence.
The first standalone release pilot then passed before the complete cohort.

## Reproduction

Build a complete runtime from source as described in [BUILDING](BUILDING.md).
Use a fresh client directory, with the new option:

```sh
python3 bridge/tools/public_render_state_catalogue.py build \
  --library build/source-local --out "$KP_WORK/source-client" --source-commands
python3 bridge/tools/public_render_state_catalogue.py run \
  --build "$KP_WORK/source-client" --out "$KP_WORK/source-gpu" --mode gpu \
  --reservation-root "$KP_LAB"
```

Run all twelve modes listed in `GPU_RENDER_STATE_CATALOGUE.md` serially, using
one shared reservation and immutable signed hosts. Stop and inspect the exact
terminal/lease if a run fails. The runner checks outputs in a fresh isolated
interpreter using frozen oracle/helper sources. Build without `--source-commands`
to reconstruct the raw-record reference with the same toolchain and runtime.

```sh
python3 bridge/tools/audit_render_source_commands.py "$KP_WORK/source-cohort" \
  --build "$KP_WORK/source-client" --reference "$KP_WORK/raw-record-cohort" \
  --out "$KP_WORK/source-audit.json"
```

The auditor verifies source/asset hashes, the actual native compilation command,
terminal signed processes, isolated validation, native image equality and every
matching raw output. It performs no GPU work.

## Remaining work

The CPU still encodes all candidate states and GPU indirect-draw predicates
select their effect. This source interface does not reduce that encoding cost;
no performance claim is made. The tested source route uses two candidates,
four slots and an ordered single writer. Other capacities, concurrent writers,
catalogue reuse, cross-allocation copies, arbitrary bindings, query/draw-index
equivalence and GPU-error recovery are not qualified.

A representative application reception and investigation of the native Apple
render-command/compiler ABI boundary remain necessary. Neither this interface
nor its tests constitute a complete modernized NVIDIA driver, general Metal
3/4 conformance or complete GTX 880M hardware coverage.
