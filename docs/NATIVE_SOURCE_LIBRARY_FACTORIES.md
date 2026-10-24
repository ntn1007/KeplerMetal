# Ordinary library and function factories for native source producers

One explicit source-library registration now connects supported native
NVIDIA-compiled CommandIR producers to ordinary Metal library, function and
pipeline factories and to the scope's automatically adapted queue. Applications
no longer register each returned producer function or manually adapt each new
consumer encoder on this route. Both the stable pointer-root ABI and the
reusable generation-tagged ABI are supported. Native pipeline compilation and
reflection remain native; no NAK producer program/carrier is required.

This extends the existing project integration to its newer native source backend.
The earlier automatic library route still selects the separately pinned NAK
program family. These paths coexist without assigning imported pipelines to
native source functions. This is level 2 opt-in application support.

## Registration and normal calls

```objc
BOOL ok = [scope registerNativeSourceCommandIRLibraryData:producerBytes
    expectedSHA256:producerSHA functionNames:producerNames
    reusableContexts:YES error:&error];
if (!ok) return;
// The registered scope owns device and queue. Root/record preparation,
// producer reservation, resource declaration and ordering are still required.
id<MTLLibrary> library = [device newLibraryWithURL:producerURL error:&error];
id<MTLFunction> function = [library newFunctionWithName:producerName];
id<MTLComputePipelineState> pipeline =
    [device newComputePipelineStateWithFunction:function error:&error];
id<MTLArgumentEncoder> arguments = [function newArgumentEncoderWithBufferIndex:0];
id<MTLCommandBuffer> buffer = [queue commandBuffer];
id<MTLComputeCommandEncoder> encoder = [buffer computeCommandEncoder];
```

This does not replace the lifecycle, catalogue or indirect-resource rules in
[REUSABLE_ICB_CONTEXTS.md](REUSABLE_ICB_CONTEXTS.md). A reusable producer must be
reserved before encoding and every consumer must complete before reset. Compile
with the workspace source lowering selected offline; registration does not
translate arbitrary existing AIR or modify installed SDKs/frameworks.

The registration snapshots the library bytes and each function name. It accepts
one through 64 unique nonempty names of at most 256 UTF-16 code units and at most
16 MiB of library data, with an exact SHA-256 identity. Every selected function
must be a native kernel without declared function constants, with the existing
dense root at buffer0: five/six 64-bit members, either pointer + UInt64 or tagged
UInt64 + UInt64, followed by three/four pointers. Native reflection supplies the
schema. The pointer context's complete base structure is validated as before.
The reusable scalar context requires explicit `reusableContexts:YES` and matching
source compilation. The wrong ABI fails before publishing the registration.

Each selected function also passes a native PSO construction/limit preflight.
Only primitive schema/profile metadata and immutable bytes are retained in the
registration. Preflight PSOs are not retained there, avoiding a potential cycle
through an interned source library and native PSO/function ownership. Later
ordinary PSO factories call the native driver again. The runtime deliberately
leaves the imported-pipeline link empty for this backend.

Failed preflight publishes no library registration or automatic queue activation.
Duplicate registration, missing functions, duplicate/invalid names, old opaque
roots and the opposite source ABI are refused. Selected functions acquire scoped
argument getters; unlisted functions in the same registered library remain
native. Other libraries retain native behavior. Registrations sharing a scope
remain keyed by the exact library hash; registering that same hash twice fails.

## Factories and asynchronous behavior

The three library constructors are `newLibraryWithData:error:`,
`newLibraryWithURL:error:` and `newLibraryWithFile:error:`. Matching file inputs
are read into an immutable snapshot before native library creation. The function
route uses all five public selectors already supported by the library adapter:
plain name, name/constants synchronously and asynchronously, and descriptor
synchronously and asynchronously. Nine test variants cover nil/empty/unused
constant values, ordinary/empty-constant descriptors and a descriptor alias.
They do not qualify specialization of a declared function constant. Unsupported
function descriptor/binary archive options retain their explicit refusals.

All six ordinary compute pipeline factory variants return native
`NVMTLComputePipelineState` objects on this backend. Requested reflection is the
native scalar/pointer schema, not the older imported-producer reflection adapter.
Supported descriptor labels and single asynchronous replies are checked. This
cohort does not add a general descriptor thread-limit repair or binary linking.

The native asynchronous implementation may itself invoke `newFunctionWithName:`
before delivering its final function. Those intermediate native objects can also
be adapted automatically. The auditor checks the requested final selector, each
permitted forwarded plain-name call, every adopted schema and exactly one client
callback. Additional automatic objects are not counted as extra client callbacks
or manual function registrations. Live function/library objects and the owned
queue are restored when the scope ends; weak records do not own the scope.

## Qualification

[Machine-readable results](native-library-factory-validation.json) give exact
counts and route combinations. The complete runtime archive is
`875cb4b9f3e30022b110709b0bd9c7fe6c0efcb58ddc19eccedbec6543c52551`.
It rebuilds all seven objects; only `KeplerCPUICB.o` changes from the preceding
qualified reusable-context archive. Environment: macOS 26.7.1 / 25G241,
SDK 26.2, clang 17, Metal 32023.864, x86_64, GTX 880M PCI `10de:1198`, exact
installed Metal driver profile `e240d54a…`.

The two zero-submission contract hosts cover both schemas, 86 checks including
22 expected refusals and **324 native factory observations**. Each schema runs
the complete metadata construction grid: three library constructors × nine
function variants × six pipeline factories. The contracts check input mutation,
partial preflight failure, unlisted-function passthrough and restoration with
live objects. They create no command buffers or GPU submissions; construction
checks are distinguished from the numerical GPU reception below.

The 38 native-library GPU processes verify **12,361,728 exact consumer uint32
values**, 3,090,432 active consumer invocations, 197,018,752 guard bytes and
16 resource-catalogue API refusals. All 640 raw stage/counter comparisons to
the matching preceding paths are identical, including 32 legacy-library files.
The reusable path preserves its 464 premature prepare/reset refusals, 60 stale
CPU-plan refusals, 80 retired-slot consumer refusals and three GPU-rejected roots.
The GPU reception uses 18 stable pointer modes and 20 reusable modes, covering
all three library constructors, all nine function variants and all six pipeline
factories for each schema. The exact pairings are recorded per case; GPU reception
is not the full Cartesian product of the metadata grid. It preserves the previous
four element counts through 32,768, template permutations, duplicate template
requirements, missing stages/producer/consumer, invalid-record controls, producer
ordering, delayed consumers, stale roots and retired slots. CPU expected answers
are not uploaded. Raw outputs, guards, counters, roots, complete contexts, native
binding images and execution witnesses are independently recomputed.

A separate 52-host baseline repeats the entire preceding reusable/native/NAK
cohort on this same runtime. Two additional GPU hosts exercise the older ordinary
NAK library registration path, including descriptor/alias/asynchronous pipeline
creation. Its example now uses the existing qualified PCI identity helper in
place of a fixed boot registry ID. This does not change its library/program pins.
The final 94-host cohort is signed, terminal and nonoverlapping. No new M1 run,
full FP64/CAS/render/video reception or performance benchmark is claimed.

The early asynchronous pilot completed successfully but its original auditor
required exactly one function adaptation. That auditor failure is preserved;
an explicit CPU-only re-audit checks the observed nested native calls and raw
results. Pilot results are excluded from final qualification. Initial failed
client syntax builds and the unused preliminary runtime build are retained
separately. Final numerical claims use the final frozen builder and oracles.

## Reproduction

The source-only runtime build and six local native fixture prerequisites are
unchanged. The optional NAK baseline requires its original pinned local programs.
The manual-push NAK bank used by the direct baseline and the native-root bank
used by ordinary legacy library registration have different carriers/programs.
`legacy_library_fixture_pins.json` verifies all 21 native-root inputs at build
time, before compilation or execution. The initially mixed-bank legacy run was
refused before any consumer trial and is preserved outside final qualification.
Neither driver files nor compiled fixtures are published in this repository.

```sh
python3 tools/build_from_source.py --out build/native-library
python3 bridge/tools/public_native_msl_commands.py build \
  --library build/native-library --assets "$LOCAL_ASSETS" --out "$NEW_BUILD" \
  --function-arguments --stable-identities --reusable-contexts \
  --library-factories --nak-baseline \
  --legacy-library-assets "$LOCAL_NATIVE_ROOT_ASSETS"
python3 bridge/tools/public_native_msl_commands.py run \
  --build "$NEW_BUILD" --out "$NEW_RUN" \
  --reservation-root "$COMMON_LAB_BRIDGE" \
  --kind library_reusable --route 2:8:5 --mode delayed_consumer
```

Omit `--nak-baseline` to build a native-only package. Kinds `library` and
`library_reusable` select their matching ABI. Routes are `library:function:pipeline`
with integer ranges 0–2, 0–8 and 0–5. See
[NativeSourceLibraryReception.inc](../bridge/tools/NativeSourceLibraryReception.inc)
for the precise mapping. `library_contracts` takes mode `pointer` or `reusable`
and has zero submissions. `legacy_library` is built only when `--legacy-library-assets` supplies its
separate pinned native-root NAK fixture bank; its targeted ordinary-library regressions use `basic`/`barrier`.
Every run requires a new output directory and the existing common host reservation.

The CPU-only aggregate auditor expects the documented 38 native-library mode runs,
two metadata hosts, two targeted legacy-library hosts and preceding baseline:

```sh
python3 bridge/tools/audit_native_library_factories.py "$COHORT" --out "$NEW_RECEIPT"
```

This connects more ordinary application calls to the scoped runtime. Native Apple
ICB/PSO resource IDs, arbitrary shader/library translation, general resource/root
schemas and transparent unmodified applications remain open. The installed driver,
OCLP, family reporting and WindowServer remain unchanged. No speedup is claimed.
