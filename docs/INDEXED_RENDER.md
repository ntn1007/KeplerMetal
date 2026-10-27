# Typed indexed draws with owned index bindings

The typed AIR path now translates both device-pointer overloads of
`metal::render_command.draw_indexed_primitives()`: 16-bit and 32-bit triangle
indices. The GPU converts the supplied pointer to a certified index offset,
preserves the existing state identity and writes the existing render record.
The native materializer enforces the complete draw envelope before execution.
Images are checked against independent CPU raster and direct native draws.

This is branch B work in the adapted application, using the installed NVIDIA
driver and native compiler. It adds no system driver, Metal family/version
advertisement, NAK producer import or transparent application integration.

## Context extension and validation

`newIndexedRenderCommandArgumentContextWithCommands:stateCatalogue:
commandRecords:commandRecordsOffset:commandBuffer:error:` snapshots the exact
live catalogue's index buffers. The existing 32-byte root header is unchanged;
reset and nonindexed producers can still use that prefix. The indexed context
adds a 32-byte `KPIX` version-one extension and an inline table:

| Binding field | Width | Meaning |
| --- | --- | --- |
| State identity | 64 bits | Scope/catalogue-owned token |
| Base address | 64 bits | Sealed index-buffer GPU address plus offset |
| Byte length | 64 bits | Sealed maximum count times element size |
| Logical slot / kind | Two 32-bit words | Target command and uint16/uint32 format |
| Maximum count / reserved | Two 32-bit words | Span consistency and zero reserved word |
| Padding | 64 bits | Must remain zero |

Each row is 48 bytes; at most 16 rows fit the existing catalogue bound. The
library owns a Private allocation containing guards, prefix, extension and rows,
and retains/declares the referenced index buffers through completion. The
qualified four-row context is 384 bytes, with table offset 128. The basic
context remains 160 bytes. API construction rejects record/index span overlap;
the argument encoder rejects a root that aliases any retained index buffer.

The shader validates extension identity, count, row size, inline-table address,
slot, state, format, alignment and pointer span. It never dereferences the
supplied index pointer. A matching pointer becomes an element offset relative
to the sealed binding. An unknown pointer/type/table clears the command rather
than replaying a stale preceding draw. A zero state identity can carry inert
geometry; it remains rejected by the materializer until a valid state exists.

The existing materializer separately checks index count, instance count, base
vertex and base instance against the selected certified state. Thus a count
outside the sealed draw envelope cannot reach the native indirect draw merely
because the start pointer matched. Context roots and resources must remain
immutable through completion; these checks are not a sandbox for arbitrary
GPU addresses or deliberate mutation of Private context memory.

## Translation and native programs

The input shader keeps its original entry arithmetic, pointer arithmetic,
branches and command order. Only supported command callees/root metadata are
lowered. The two indexed overloads and reset are accepted; other primitives,
constant-address-space overloads and resource/pipeline setters refuse.

The exact original AIR hash is
`fe2f89f4f01a791babd17415e12ad4ad43ec172c8536dc1c5c50408a093273af`;
normalized IR hash is
`5483170015aa7e576a88bea00b71013068b554ae1d2bcf90a5f772999cb98109`.
The standalone host is compile-time restricted to construction-only inspection.
It cannot dispatch these kernels without the render harness's owned resources.
Both native programs are inspected and certified before execution:

| Program | Bytes | SHA-256 |
| --- | ---: | --- |
| Translated typed shader | 12,928 | `d7d11afc0e4d2c908d377257bd4a230cf85451c3a254708f3078d4f7fa7e42e2` |
| Independent native MSL reference | 13,568 | `a83486b8e804cd3c50f5a08cef4f5cdeb300dcea87dc650e66e1bb535c0dd059` |

No unresolved native CALL is present. These are larger programs with native
compiler-managed local storage; compilation/inspection alone is not execution
or performance evidence. The actual signed dispatches and image controls below
are the execution reception.

## Reception layout

Two fresh-process series cover all eighteen modes:

- `indexed_gpu`, direct `indexed_native`, and native-MSL `indexed_reference`.
- Missing dispatch, foreign buffers, deliberately mismatched pointer formats,
  and a basic context with the indexed table absent, each with a native image
  reference where applicable.
- Last indexed draw wins, reset before draw and reset after draw, with native
  image references. Resets distinguish inert geometry from an empty command.
- `indexed_contracts`: mixed Shared/Private index inputs and two CPU refusals
  before submission (record/index overlap and root/index alias).

Every host covers eight frames, signed base vertex `-2`, both index widths,
complete six-index rectangles, zero-count draws, rejected count/start spans,
unknown state identity and missing preceding production. Each frame checks the
full inline table/guards, produced records, materialized arguments/reasons,
arithmetic witnesses and pixels. Candidate state choices and records are never
read on CPU to decide its draws; direct references use known input recipes.

Ordinary PSO construction stays native. Their own staging programs are checked
against certificates before dispatch, with no constructor observer installed
for those calls. The initial inspection observer is restored before scope
activation. Scope/ICBs and argument encoders are released before commit while
the owned context remains live; function getters are restored. Those lifetime
checks extend the [existing root contract](RENDER_RECORD_ARGUMENTS.md).

Exact counts, controls, legacy/compute regressions, source rebuild and system
hashes are in [validation](indexed-render-validation.json) and
[source chain](indexed-render-source-chain.json). Pilot and construction-only
hosts are inventoried separately from the final reception. This phase changes
only the ICB object in the complete seven-object runtime.

## Measured reception

On October 24, 2026, 36 signed, nonoverlapping test processes produced 288
frames on the GTX 880M. All 3,538,944 float channels matched their CPU oracle
with maximum error zero. The cohort includes 256 indexed producer dispatches,
1,024 checked arithmetic words and four expected API refusals. Across two runs,
normal rendering differs from the no-dispatch, foreign-binding and last-draw
controls in the frames documented in the validation file. These controls and
the Private-buffer readbacks complement the native-program inspections.

Thirteen additional signed processes rechecked earlier render and compute
paths: 32 frames and 2,291,712 exact uint32 results. The public source export
passes 324 CPU unit tests. Its seven compiled runtime objects and both client
executables match the qualified builds; the static archive members match,
although archive metadata differs. The system audit found 87 inventoried files
unchanged. Two preliminary CPU-only builds failed before GPU submission and
were corrected; their logs are preserved with the private evidence.

These are correctness and integration results, not a performance benchmark.

## Reproduce

Use the qualified Xcode/Metal profile, local envytools, fresh paths and one
shared host reservation. Source-only compilation submits no GPU work:

```sh
python3 tools/build_from_source.py --out build/indexed-runtime
python3 bridge/tools/public_air_indexed_render.py build --out /absolute/indexed-producer
python3 bridge/tools/public_air_indexed_render.py inspect \
  --build /absolute/indexed-producer --out /absolute/inspections/inspect-lowered \
  --variant lowered --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_indexed_render.py certify \
  --run /absolute/inspections/inspect-lowered --envydis /absolute/envytools/envydis
```

Repeat inspection/certification for `reference` before using it. Then:

```sh
python3 bridge/tools/public_render_state_catalogue.py build \
  --library build/indexed-runtime --out /absolute/indexed-render-build \
  --air-reset-build /absolute/indexed-producer \
  --air-reset-inspections /absolute/inspections \
  --render-argument-encoders --typed-indexed-render
python3 bridge/tools/public_render_state_catalogue.py run \
  --build /absolute/indexed-render-build \
  --out /absolute/session/cohort/0/indexed_gpu --mode indexed_gpu \
  --reservation-root /absolute/common-lab/bridge
```

Create parents first. Run all modes in `verify_indexed_render.py:MODES`
sequentially under `cohort/{0,1}/{mode}`; never replay a failed/unresolved host
without inspecting its exact receipt. Recompute the final reception:

```sh
python3 bridge/tools/audit_indexed_render.py /absolute/session \
  --build /absolute/indexed-render-build \
  --previous /absolute/preceding-draw-session/render-cohort/0/draw_no_dispatch \
  --out /absolute/new-audit.json
python3 -m unittest discover -s tests -v
python3 tools/check_publication.py
```

The previous-image comparison reanalyzes archived data, not new GPU execution.
Native index-pointer lookup and signed geometry are qualified on the tested
four logical slots/two states, not every accepted catalogue combination.
Remaining work includes typed pipeline/resource setters, broader bindings and
transparent ordinary-application integration. No Metal 3/4 conformance,
hardware-video qualification or performance gain is claimed.
