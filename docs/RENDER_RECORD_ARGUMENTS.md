# Public argument encoders for owned render-command roots

The typed AIR render-reset producer now obtains its root through
`MTLArgumentEncoder.setIndirectCommandBuffer:atIndex:`. The library constructs
the context header, exports its pointer, declares indirect resources and holds
the context/root buffers through command-buffer completion. The adapted client
no longer constructs a GPU context or address root. This extends branch B's
render path; it does not change the installed NVIDIA driver.

## Contract and native boundary

After enabling the existing render catalogue/materializer, register an immutable
lowered metallib with `newRenderCommandFunctionWithLibraryData:expectedSHA256:
functionName:rootBufferIndex:error:`. Its returned object is a real native
function. Only its two root argument-encoder getters are adapted. Ordinary
`newComputePipelineStateWithFunction:error:` stays native, without instruction
substitution or a constructor observer during that call.

Create a `KPRenderCommandArgumentContext` using the target ICB, its state
catalogue, the live Private record buffer/offset and the retained recording
command buffer. Only the catalogue's first execution ICB is supported, with
capacity at most 16 and 64-byte records. The context belongs to that scope,
thread, queue and command buffer; it is single-preparation, not compute IRv2.

Three public getter routes are qualified:

- The registered function's simple root getter.
- Its getter with reflection: the returned native reflection remains scalar
  `ULong`, size/alignment eight, as compiled. Original Apple ICB metadata is
  **not** fabricated.
- The scoped device descriptor factory with exactly one ICB at index zero,
  array length one. Ordinary pointer descriptors retain native behavior.

The returned encoder has encoded length/alignment eight. Set a bounded Shared
argument-buffer span, then its owned ICB at index zero. The library writes the
project context pointer. The one-element array setters and encoder rebinding
are qualified; rebinding preserves the preceding exported root.

Before dispatch, call `prepareRenderCommandArgumentContext:argumentBuffer:
offset:computeEncoder:commandBuffer:error:`. It verifies the exported eight
bytes, binds root zero, declares the Private context/records and seals the
context. Ordinary output/index/config buffers remain the client's bindings.
Keep Shared root bytes immutable until completion. Retention cannot prevent a
client from writing directly to Shared memory after validation.

The context uses the preceding project's 32-byte header in a guarded Private
allocation. It does not implement Apple's native ICB resource ID or command
packets. Record materialization still expands CPU-certified state candidates
and uses native indirect-draw predicates. Integration remains level 2: adapted
applications explicitly install a scope and prepare their producer.

## GPU reception

Three repeats of nine modes give **27 signed, terminal, nonoverlapping hosts**:
`arguments_gpu`, `arguments_native`, `arguments_device`,
`arguments_reflection`, `arguments_arrays`, `arguments_reuse`,
`arguments_no_reset`, `arguments_no_reset_native`, `arguments_contracts`.

The independent raster/readback oracle verifies:

- **216 frames / 2,654,208 float channels**, maximum error zero.
- **168 reset dispatches / 672 exact uint32 arithmetic witnesses**.
- 216 independently read snapshots of the ordinary native PSOs, each matching
  the certified 1,280-byte reset program SHA-256
  `812fda6d08d40f5cc0974bdd46ab0bdf51f04fe3c8f8ddee0e308c8be93d9b06`.
  These are program-identity checks, not separate dispatch counts.
- 169,728 raster/materializer guard bytes and 113,664 reset/root guard bytes.
- 168 reference/control image pairs, 216 image pairs against the previously
  qualified manual-root path, 144 repeat images and 4,368 repeat readback pairs.

These GPU frames use capacity four and root zero at byte offset 64. The API's
upper bound of 16 records is a validation bound, not qualification of every
capacity, root schema or possible shader.

Reset changes exactly frames 0/1/3/4/6, for 19,992 differing float channels
against the missing-reset control across three repeats. Other frames remain
unchanged for the previously documented empty/rejected-draw reasons.

All final frames release the argument encoder and restore the function getters
before commit. Existing scope/ICB release checks remain; the completion lease
keeps contexts alive despite those releases. Twenty-two ordered contract
refusals per contracts host cover registration, root shape, wrong ownership,
thread/queue/command-buffer identity, tampering, duplicate preparation and
post-restoration setters. Malformed roots are never dispatched. Ordinary
pointer descriptors and non-root function getters are checked for passthrough.

The same new seven-object runtime passes **16 additional regression hosts**:
seven preceding AIR-render modes (56 frames / 688,128 float channels), and nine
compute IRv2 cases (2,291,712 exact uint32 results / 572,928 consumer invocations).
These include library factories, pointer/reusable roots, encoder reuse, delayed
consumers, stale generations and zero-submission contracts. Only the ICB object
changes; the other six runtime objects stay byte-identical.

Two successful eight-frame pilots are excluded from final reception totals.
One earlier zero-dispatch native reflection observation terminated successfully,
but its launcher postprocessing lacked a colocated module: its recovered job
record is preserved separately, without inventing a standard execution receipt.
There are 46 actual terminal nonoverlapping hosts in this phase: 27 reception,
16 regression, two pilots and that metadata observation.

All **287 CPU tests** pass. All **87 inventoried system files** remain unchanged.
An archive of the public sources rebuilds all seven objects byte-identically.
Only archive header metadata differs; the resulting linked application, MRC
certificate helper and assets match the GPU-tested build exactly. The separate
producer also rebuilds identically, apart from an IR dump's first ModuleID path.
Exact artifact/source hashes, public rebuild checks and limitations are recorded
in [validation](render-record-arguments-validation.json) and
[source chain](render-record-arguments-source-chain.json).

## Reproduction

Use the exact Xcode/Metal profile and producer/certificate prerequisites from
[AIR_RESET_DATAFLOW.md](AIR_RESET_DATAFLOW.md). Fresh public source builds:

```sh
python3 tools/build_from_source.py --out build/render-arguments-runtime
python3 bridge/tools/public_render_state_catalogue.py build \
  --library build/render-arguments-runtime --out /absolute/new-render-build \
  --air-reset-build /absolute/qualified-producer-build \
  --air-reset-inspections /absolute/producer-session \
  --render-argument-encoders
python3 bridge/tools/public_render_state_catalogue.py run \
  --build /absolute/new-render-build \
  --out /absolute/render-session/cohort/0/arguments_gpu \
  --mode arguments_gpu --reservation-root /absolute/common-lab/bridge
```

Create parents first; use new result directories, the same reservation and
strictly sequential hosts. Run every listed mode under `cohort/{0,1,2}/{mode}`.
Stop on any failed or unresolved signed host. Then recompute reception:

```sh
python3 bridge/tools/audit_render_record_arguments.py /absolute/render-session \
  --build /absolute/new-render-build \
  --reference /absolute/previous-air-render-session/cohort/0 \
  --out /absolute/new-audit.json
python3 bridge/tools/audit_render_record_regression.py /absolute/render-session \
  --out /absolute/new-regression-audit.json
python3 -m unittest discover -s tests -v
python3 tools/check_publication.py
```

The second auditor expects `legacy-render-build`, `compute-regression-build`
and `regression/{render,compute}`. The render builder without the new opt-in flag
reconstructs the legacy host. The native MSL compute builder uses
`--function-arguments --stable-identities --reusable-contexts --library-factories`
and the six pinned local native fixtures described in
[NATIVE_SOURCE_LIBRARY_FACTORIES.md](NATIVE_SOURCE_LIBRARY_FACTORIES.md).
Its nine exact kind/mode/route combinations are in the auditor's `COMPUTE` tuple.
Archived reference reanalysis is distinct from new GPU execution.

No NAK producer, system deployment, speedup, M1 comparison, general Metal 3/4
conformance or transparent application integration is claimed. Library-level
registration of additional typed command operations and broader supported root
schemas are next; each needs its own translation, contracts and GPU reception.
