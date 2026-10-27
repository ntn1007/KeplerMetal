# Architecture

## Branch A: native NVIDIA behavior

`KeplerProgramImport` preserves the retained-return C API as a facade over the same MRC constructor transport used by `KeplerNativeCAS`. Generic compute, graphics, FP64 and certified CAS imports share its mutex/context, strict driver/PCI checks and constructor restoration; nested imports and cached no-callback pipelines are refused. [Reception and build contract](SHARED_GENERIC_IMPORT.md). `KeplerNativeCAS` recognizes a bounded native shader defect and applies a certified process-local repair. `KeplerNativeCommands` and `KeplerNativeRenderDraws` handle narrowly qualified native command/profile data.

The installed driver continues to allocate resources, submit work and manage the device. No kernel driver or system framework is replaced. Linux/FreeBSD references help identify possible future improvements; their proprietary implementations are not part of this code.

## Branch B: Metal resources and commands

`KeplerCPUICB` installs scoped behavior on objects belonging to an adapted client. The CommandIR headers, plan/scope includes and materializer kernels define explicit command contracts, lifetime ownership, binding validation and dispatch boundaries. The argument/function encoder includes preserve native metadata and route only the registered subset to the experimental implementation. Restoration is tested explicitly.

Compiler experiments use an external OpenNVDA AIR frontend, Mesa NIR/NAK and SM30 code generation. An alternative compiler is one tool in the chain; it does not implement new Metal command queues, resource identity or feature-family conformance by itself.

The native-resource lowering maps the producer's root pointer and launch dimensions to the established CB1 resource table. `KeplerCommandIRProducerFactory` calls the existing ownership-correct import transport. After exact source/carrier/program registration, the scope serves six synchronous/asynchronous function and descriptor factory variants and returns actual native PSOs. Reflection requests create an adapter around native argument/type metadata. Descriptor imports snapshot supported properties, while unsupported properties and inconsistent native thread limits are refused. Other functions take the original native path. No installed driver or family capability is changed. See [the bounded API contract](NATIVE_FUNCTION_PIPELINES.md).

The render-record root uses a separate single-ICB argument schema and owned Private context, rather than compute IRv2 or Apple resource IDs. Public encoder setters populate a Shared root; explicit preparation checks its immutable snapshot and declares indirect resources. Command-buffer completion retains the roots/context after scoped function restoration and owner release. Ordinary native PSO creation and compiled scalar reflection are preserved. [Qualified contract](RENDER_RECORD_ARGUMENTS.md).

The opt-in typed draw translator reuses the reset root-metadata decoder and owned render context. It preserves original AIR entry dataflow while lowering literal triangle draw/reset intrinsics to checked record writes; native code is inspected and pinned before execution. Record materialization enforces the existing certified state/geometry envelope. [Contract and raster reception](TYPED_RENDER_DRAW.md).

Indexed render producers use an optional inline binding-table extension after the unchanged v1 root header. Scope/catalogue-owned rows bind state/slot/index format to sealed GPU address spans; the shader maps pointers to element offsets, then the existing materializer checks complete geometry bounds. The context retains and declares index resources through completion. [ABI and reception](INDEXED_RENDER.md).

## Integration levels

1. Laboratory application explicitly calls experiment functions.
2. Adapted applications use the documented experimental interfaces and contracts. **Current implementation level.**
3. Ordinary Metal applications use added behavior transparently. **Open work.**

No feature-family/version spoofing is used. A feature needs SDK availability, frontend acceptance, advertised capability, pipeline creation, actual execution, correct output, limitations and performance considered separately.

## Profiles

The runtime contains exact device/registry checks, driver hashes, private class names, offsets and immutable library/program pins. Those are the observed reference ABI, not a universal NVIDIA/macOS ABI. They deliberately reject unqualified environments. On another GTX 880M, review and qualify a new profile rather than deleting these guards.

Source layout:

- `bridge/src/`: runtime, original MSL kernels, profile descriptions and upstream patches.
- `bridge/tools/`: lab builders, bounded runners, CPU oracles and historical reporting tools.
- `bridge/sdk*/examples/`: adapted-client source examples; binary SDK assets are omitted.
- `driver-research-2026-10-13/tools/`: historical inventory/comparison scripts; downloaded inputs omitted.
- `legacy/`: early compatibility prototype for context, outside the supported source build.
- `tools/`: standalone public build, local inventory, reference retrieval and publication checks.

## Thread-limit initialization and encoding checks

The qualified native pipeline class has a 64-bit `maxTotalThreadsPerThreadgroup` field at offset 88 (instance size 104). For approved imported producers, the descriptor path initializes that field to the supported explicit limit. Driver identity, class, type, offset, existing value and unchanged getter are checked before/after the write. It changes no program bytes or optimizer decisions. Adapted encoders track the current PSO and check local-size products before direct, grid-thread or indirect dispatch calls; switching to an ordinary pipeline clears that constraint. This is scoped process-side repair and validation, not a global driver replacement. The application must use an adapted encoder before binding the limited pipeline; the registered scope-owned queue now provides this through ordinary factory calls.

## Scope-owned automatic compute factories

`KeplerAutomaticComputeFactories.inc` forwards normal queue and compute factory calls, then adapts newly published objects while the scope remains active. It uses weak associations and weak buffer records; the scope owns a separate synchronization object so restoration during deallocation does not retain the scope itself. Native allocation occurs outside that lock. A later adaptation/publication step serializes with restoration, and saved wrapper IMPs fall back to the exact native class after their associations have been cleared.

The scope-owned queue keeps its original instance layout (688 bytes), as do its command buffers (656 bytes) and compute encoders (128 bytes). These numbers belong to the pinned driver ABI. Other queues, existing buffers, shared native class implementations, retention flags and family/version reporting remain outside the adaptation.

## Ordinary library and function creation

`KeplerCommandIRLibraryScope.inc` snapshots one approved source library, carrier and six programs, validates their pins and prepares native pipelines before publishing immutable profiles. `KeplerCommandIRLibrary.inc` forwards three ordinary device library factories and five native function factories. Native functions are created by the existing compiler/runtime, retain their metadata and names, and acquire the matching program profile. A descriptor alias resolves through the source name. No new shader is compiled from arbitrary application input.

Matching file/URL construction uses the same immutable bytes that were hashed. Profiles hold primitive schemas and native PSOs rather than source functions, avoiding a library/function ownership cycle. Library/function records and scope links are weak; live native objects are restored when the scope ends. Registration activates the existing queue and pipeline integration. Source lookup, command execution, native-compiler correction and installed-driver modernization remain separate claims.

## Native allocation for private scratch and spills

`KPCreateLocalMemoryPipeline` uses the existing MRC CAS/approved-import serialization. It snapshots one pinned carrier, verifies native private-frame fields, checks the compiled scratch requirement against capacity and preserves the native local allocation. Instruction count/GPRs are updated; the existing qualified word11=576 control reserve is applied separately. The decoded combined allocation and spill metadata must match before dispatch. The scoped thread-local contract and immutable carrier state are cleared in `@finally`, including rejected imports. Local→descriptor→CAS regression checks cover their coexistence. This adds a compiler/backend resource path; the installed driver and feature-family queries remain unchanged. [Contract](LOCAL_MEMORY.md).
