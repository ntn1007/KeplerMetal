# KeplerMetal

A combined adapted-client path now brings typed pipeline and vertex setters together with indexed draws. [Contract and evidence](docs/TRIPLE_RENDER.md).

The scoped typed vertex-buffer setter now selects between certified render states in an adapted application. [Evidence and limits](docs/VERTEX_BINDING_EXPERIMENT.md).

**Ultimate goal: develop a modernized NVIDIA driver for macOS that makes full use of Kepler's hardware capabilities and supports as many Metal features as the hardware can actually implement.** The reference GPU is a GeForce GTX 880M, GK104 / SM30, with 8 GiB VRAM in an Intel iMac.

The long-term target is native macOS integration, allowing ordinary Metal applications to use these capabilities without application-specific adaptations. Progress is measured through correct GPU execution, stability and workload-specific benchmarks.

The work follows two complementary tracks:

1. **NVIDIA driver modernization:** diagnose and correct native compiler/runtime behavior, improve GPU and memory management, command submission and synchronization, and validate stability and performance.
2. **Metal feature support:** extend compiler, runtime, resource and command functionality, evaluating Metal 2/3/4 features individually against the hardware's actual capabilities.

**Current stage: experimental research and validated prototypes.** This repository shares readable code, targeted fixes, reproduction tools and GPU evidence toward that driver. Current integration still requires adapted applications; a complete replacement system driver and general Metal 3/4 support remain work to be done. Proprietary Apple/NVIDIA components are obtained separately and are not redistributed here.

[Français](README.fr.md) · [Build from source](docs/BUILDING.md) · [Dependencies](docs/DEPENDENCIES.md) · [Status](docs/STATUS.md) · [Architecture](docs/ARCHITECTURE.md)

A calibrated, process-local observer compares ordinary Metal buffer allocations on the GTX 880M: a warmed 4 MiB target coincides with one additional IOAccelerator resource creation, while a 4 KiB target does not in the observed traces. Resource identity, deletion and GPU execution remain unproven. [Evidence and reproduction](docs/VIDEO_METAL_RESOURCE_OBSERVER.md).

## Recent progress

Two guarded processes created and released an empty real video-context wrapper attached to Metal’s GTX shared object; video decoding remains unproved. [Evidence](docs/METAL_VIDEO_CONTEXT.md).

A process-local observer verifies the device-to-shared object link created naturally by Metal on the GTX; lifetime and video use remain unqualified. [Evidence](docs/METAL_SHARED_OBJECT.md).

A synthetic legacy-video initialization probe uses observed device words and checks an ordered locally intercepted selector sequence; hardware decoding remains unproved. [Evidence](docs/VIDEO_SYNTHETIC_SEQUENCE.md).

A process-local Metal observer now validates five configuration words from a real GTX device object; their meanings and video compatibility remain unknown. [Evidence](docs/METAL_DEVICE_OBJECT.md).

Read-only analysis narrows the current device-configuration boundary to a type check and five 32-bit outputs; the valid object and values remain unqualified. [Evidence](docs/IOACCEL_DEVICE_CONFIG.md).

A bounded synthetic video-provider probe reaches a locally refused `0x103` request after fabricated device configuration. [Evidence and limits](docs/VIDEO_SYNTHETIC_SELECTOR.md).

A guarded synthetic video-provider probe reaches a device-configuration dependency after a fabricated fence response; no hardware video is claimed. [Evidence and preserved failure](docs/VIDEO_SYNTHETIC_CONFIG.md).

An offline comparison exposes a video-provider/kernel dispatch difference that must be resolved before a historical provider can be integrated. [Evidence and limits](docs/VIDEO_PROVIDER_DISPATCH.md).

A scoped historical re-audit identifies an installed NVIDIA video-provider Create stub on a deliberately selected legacy path; hardware decoding remains unavailable. [Evidence and limits](docs/VIDEO_LEGACY_BACKEND.md).

A second pinned client qualifies the same CAS repair through the public default compute-descriptor factory. [Evidence and limitations](docs/DESCRIPTOR_CAS.md).

An explicitly launched public-Metal test client now receives the qualified native CAS repair from a process-local bootstrap without linking KeplerMetal. [Evidence and limitations](docs/STANDALONE_CAS.md). A [scoped launcher](docs/CAS_LAUNCHER.md) now checks the client policy and artifacts and reserves the GPU for an explicitly selected process; other applications remain unqualified.

The current-profile native CAS SDK now builds with regenerated decoder-checked certificates and a PCI-identified GTX client; two repaired runs and native defect controls have independent CPU oracles. [Evidence and limits](docs/CAS_SDK_REGENERATED.md).

The native CAS diagnosis now requires complete instruction coverage and an exact pinned-decoder replay, preventing two demonstrated false acceptances from corrupted listings. [Evidence and remaining limits](docs/CAS_DISASSEMBLY_COVERAGE.md).

The opt-in standalone experiment now handles repeated and concurrent default-device requests while preserving its exact client and library pins. [Evidence and limits](docs/STANDALONE_ICB_MULTICALL.md).

The bounded partial-grid adapter can sequence two distinct certified compute pipelines in one registered library. A GTX producer/consumer test checks the output and ordering; this is process-local support, not native Metal ICB or a system driver replacement. [Contract and reproduction](docs/PARTIAL_ICB_DUAL_PIPELINE.md).

The bounded partial-grid project ICB now also executes a pinned read/write neighbor transform, with GPU results checked against a CPU oracle. [Evidence and limits](docs/PARTIAL_ICB_BUFFER_STENCIL.md).

An explicitly enabled project ICB path now executes bounded partial 1D/2D/3D grids on the GTX for a pinned shader and resource profile; arbitrary-shader support remains open. [Contract and evidence](docs/PARTIAL_ICB_BOUNDED_PROFILE.md).

The scoped CPU compute ICB accepts evenly divisible thread-grid dispatches, with bounded 1D, 2D and 3D GPU qualification. Partial grids outside the explicitly bounded profile remain refused. [Contract and GPU evidence](docs/UNIFORM_THREAD_ICB.md).

The existing Metal driver passes three GPU read/write trials on a 4 MiB buffer after purge and restoration, with three native controls and a no-dispatch control. This does not establish memory reclamation or a speedup. [GPU contract and evidence](docs/VIDEO_METAL_PURGE_GPU.md) · [CPU-only observations](docs/VIDEO_METAL_PURGE.md).

An opt-in scope can automatically adapt qualified ordinary render-encoder factories on its own queue. A separately compiled public-Metal client renders correctly; unsupported passes guard project ICBs. [Evidence and limits](docs/AUTOMATIC_RENDER_FACTORIES.md).

A scoped client now combines GPU selection of pipeline, vertex and fragment resources with indexed rendering. [Contract and evidence](docs/QUAD_RENDER.md).

The adapted render catalogue supports eight certified states and sixteen flattened candidates. GPU witnesses and native images qualify the expanded path. [Evidence and limits](docs/EIGHT_STATE_CATALOGUE.md).

A scoped typed fragment-buffer selector now switches genuine Metal texture argument resources in an adapted GTX client. [Contract and evidence](docs/FRAGMENT_BINDING_EXPERIMENT.md).

A scoped adapted client now combines pipeline selection, vertex-buffer changes and 16/32-bit indexed draws in one producer. [Contract, tests and limitations](docs/TRIPLE_RENDER.md).

The scoped runtime now owns typed render-pipeline tokens, retained resources and a two-word argument encoder. GPU rendering and same-runtime regressions pass; ordinary applications still require adaptation. [Contract, evidence and limits](docs/PIPELINE_RUNTIME_INTEGRATION.md).

A typed render-pipeline selector now changes a real GTX image in an explicitly adapted laboratory client. CPU, native-image and negative controls qualify this bounded case; automatic application integration remains open. [Evidence and reproduction](docs/TYPED_PIPELINE_RENDER.md).

A GTX/M1 comparison identified the original boundary for typed render-pipeline arguments. [Evidence and limits](docs/RENDER_PIPELINE_BOUNDARY.md).

Typed indexed triangles now resolve 16/32-bit index pointers through an owned binding table, then reach native indirect rendering. The source keeps signed base vertices and command order; foreign buffers, wrong formats, absent tables and overlap are checked. [Contract, reception and source-only reproduction](docs/INDEXED_RENDER.md).

SDK-typed triangle draws now translate to the owned render-record path while preserving dynamic draw arguments and reset order. The producer and resulting images are checked against independent CPU/native references; native PSO construction and the seven-object runtime are preserved. [Contract, controls and reproduction](docs/TYPED_RENDER_DRAW.md).

Public argument encoders now bind the typed render-reset producer to an owned context, without client GPU-address construction. A new runtime passes 27 reception hosts / 2,654,208 exact float channels and 16 render/compute regression hosts; native PSO creation stays native. [Contract, ownership and reproduction](docs/RENDER_RECORD_ARGUMENTS.md).

The translated typed reset producer now changes a real rendered image through the existing state-record pipeline. A 21-process reception checks 168 images / 2,064,384 float channels exactly, including direct-draw references, a native MSL reset reference and missing/invalid-context controls. The seven-object runtime stays unchanged. [Ordering, ownership and reproduction](docs/AIR_RESET_RENDER.md).

AIR reset lowering now preserves a typed producer's arithmetic, branches, index permutation and ordinary buffer bindings. Three native candidate/reference pairs pass 96 total dispatches, 1,548 exact uint32 outputs and 300 record resets. Structural recognition also rebuilds the first qualified shader byte-identically; GPU use still requires an exact qualified input. [Evidence and limits](docs/AIR_RESET_DATAFLOW.md).

An unchanged SDK-typed render-reset shader now executes on the GTX through an exact-profile AIR translation and NVIDIA's native compiler. Three translated/reference pairs pass 84 total compute dispatches and 138,240 CPU-checked bytes, with missing-dispatch and malformed-context controls. The caller still supplies a project context; Apple ICB ABI and transparent application integration remain open. [Contract and reproduction](docs/AIR_RENDER_RESET.md).

Private native code buffers now have guarded Metal-blit readback before/after uncommitted encoding. A 60-host diagnostic cohort checks 56 matching readbacks and confirms the raw command entry call remains in the observed bytes; no suspect compute CB is submitted. [Evidence and limits](docs/NATIVE_COMMAND_BINDING_READBACK.md).

A new construction-only compiler investigation separates the native ICB metadata refusal from raw diagnostic PSO acceptance and captures the resulting native programs before/after construction. Native ICB execution remains unqualified. [Evidence and reproduction](docs/NATIVE_COMMAND_COMPILER_BOUNDARY.md).

Native source shaders can now write, copy and reset certified render commands through an explicit project interface, compiled by NVIDIA’s native backend. A twelve-process GTX reception checks 1,093,632 exact float channels and matches the raw-record reference. This remains an adapted-application interface with CPU-expanded state candidates. [Contract and reproduction](docs/NATIVE_RENDER_SOURCE_COMMANDS.md).

The GPU now chooses among certified render pipeline/resource candidates, with separate pipeline-only and resource-only controls. A 54-process reception checks 1,093,632 new exact float channels and 33 native-reference image pairs. The CPU encodes candidate states and GPU indirect-draw predicates select their visible effect; no speedup is claimed. [Contract, mechanism and reproduction](docs/GPU_RENDER_STATE_CATALOGUE.md).

GPU-generated render draw arguments now pass the scoped public indirect-range route, including GPU validation of malformed scalar records. A 42-process reception covers 638,976 new exact raster channels and nonempty rendering after scope/ICB destruction; pipeline and resource bindings remain CPU-certified. [Contract, evidence and reproduction](docs/GPU_RENDER_COMMAND_RECORDS.md).

GPU-controlled render execution ranges now work through the scoped public indirect-range selector, with an explicit prepass. A new complete runtime passes 983,040 raster-channel checks, 48 native-reference image pairs and compute/FP64/CAS/render regression. This still uses CPU-encoded render commands and adapted applications. [Contract, evidence and reproduction](docs/GPU_RENDER_EXECUTION_RANGES.md).

GPU-generated compute commands now select between two native texture/sampler/nested-buffer argument banks. The 18-process native-source cohort checks 16,224 exact texture values, records, GPU binding tables and missing-stage controls; ten direct/CPU-ICB processes cover regression. The runtime remains unchanged, and the four auxiliary shaders rebuild from public source. [Contract and reproduction](docs/GPU_ICB_TEXTURE_ARGUMENTS.md).

The existing CPU-encoded compute ICB path now has native texture/sampler argument-buffer qualification: 31 terminal hosts, 72 consumer dispatches and 32,448 exact computed values, with direct/ICB comparisons, mip-view/addressing controls and full guards. The runtime stays unchanged; callers retain and declare indirect resources. [Evidence, limits and reproduction](docs/ICB_TEXTURE_ARGUMENTS.md).

One native source-library registration now enables ordinary library/function/pipeline factories and automatic compute encoders for both pointer and reusable roots. Native PSO compilation/reflection stay native; no per-function registration or NAK producer import is needed on this route. The scoped application integration and its controls are documented [here](docs/NATIVE_SOURCE_LIBRARY_FACTORIES.md).

Reusable compute ICB contexts now keep one owned GPU buffer across completed generations, reject stale CPU plans/GPU roots and track pending consumers. The 20-process reusable cohort checks 6,411,264 exact native consumer results; the full 52-process reception includes the preceding 32-process regression. This remains an adapted-application extension, with no installed-driver change or speedup claim. [Lifecycle, controls and reproduction](docs/REUSABLE_ICB_CONTEXTS.md).

Stable scope-owned pipeline identities now resolve on the GTX despite template permutations and duplicate local-size variants. A final 32-host matrix checks 5,950,464 native consumer results, retired-scope ID refusals and both NAK references. These are project ABI identities; native Apple ICB/PSO resource IDs and transparent applications remain open. [Contract, source and evidence](docs/STABLE_PIPELINE_IDENTITIES.md).

Native source-lowered producers now bind through the real function’s public argument-encoder getters and the existing owned resource catalogue, while all six pipeline factory variants stay native. This removes manual argument-root construction in the adapted client; stable ICB/pipeline identities and transparent applications remain open. [Contract and reproduction](docs/NATIVE_SOURCE_FUNCTION_ARGUMENTS.md).

A new opt-in source lowering compiles supported `compute_command` producers through NVIDIA’s native backend, then executes the existing GPU command-record pipeline. Sixteen native processes pass 5,035,008 consumer uint32 checks; 48 stage/counter files match the prior NAK reference. A 23-case record probe exposed and corrected an address-representation mismatch through registered readonly-member lowering. This is adapted-client CommandIR support, not Apple’s native ICB ABI or a system-driver replacement. [Implementation, controls and reproduction](docs/NATIVE_MSL_COMMANDS.md).

Native texture/sampler `gpuResourceID` values now have a direct-binding GPU qualification: 90 dispatches, 48,672 checked words and 18 byte-identical native/direct output pairs, without the KeplerMetal runtime or NAK. The tested older-operation shader also runs when compiled as MSL 3.0/4.0; this is not Metal 3/4 conformance. A native ICB kernel is refused specifically at `air.command_buffer` argument metadata. [Evidence, limits and reproduction](docs/NATIVE_RESOURCE_IDENTITIES.md).

Generic compute, vertex, fragment and tessellation imports now share the CAS transport’s constructor lock and restoration checks. A fresh complete archive passes 39 reception processes, 270,336 raster channels and 52,576 tessellation values with CPU oracles and explicit nested/cache refusals. [Source build, evidence and scope](docs/SHARED_GENERIC_IMPORT.md).

FP64, CPU-encoded indirect commands and native draw adapters now use the qualified exact-profile/PCI identity checks. A new seven-object archive passes 1,269 FP64/conversion dispatches with 6,095,853 checked results, 29,440 repaired CAS operations through ICBs, and 135,168 render channels. Missing-producer/native-defect controls remain explicit. [Artifact, reproduction and remaining limits](docs/ADAPTER_PROFILES.md).

The signature-only driver change and changed boot registry ID are now handled by an exact second profile and PCI-based identity. A new seven-object archive passes 190 compute dispatches, 570,616 exact uint32 results and 106,650 correct CAS operations, with a verified memory-accounting ledger. That initial cohort covered compute/CAS; the additional adapter qualification is described above. No system driver or performance change is claimed. [Profiles](docs/DRIVER_PROFILES.md) · [Results and reproduction](docs/MEMORY_ACCOUNTING.md).

The opt-in local-memory import now accepts qualified 8/16 KiB private frames. A fresh seven-object build from public sources passed 226 GTX 880M compute dispatches, 612,120 exact output values and the CAS coexistence controls. [Reproduction, artifact hashes and limits](docs/LARGE_LOCAL_MEMORY.md). This extends the experimental import path; no system driver or performance improvement is claimed.

An optional SDK batch now snapshots native records and honors completion boundaries, including source-slot `setBarrier`. Four-entry batches interleave correctly; split batches preserve the requested atomic ordering. The laboratory qualification covers 292 correct dispatches, with a separate public-artifact qualification. [API, source-only commands and limits](docs/NATIVE_RESIDENT_BATCH.md). The human administrator port experiment also passed open/close; hardware video remains unproved. [Access evidence](docs/VIDEO_ADMIN_ACCESS.md).

Two native NVIDIA-compiled kernels now have interleaved lifetimes on the GTX 880M with independent descriptor/constant state. The bounded laboratory prototype passed 34/34 candidate pairs; a separate rebuild from public sources passed 16/16 pairs and 62 correct dispatches including its serial controls. The ordinary Metal encoder remains serial; no performance gain is claimed. [Sources, controls, evidence and reproduction](docs/NATIVE_RESIDENT_OVERLAP.md).

Native decoder start is now observed through unchanged public calls and policy-call stacks. Three final cases create the first CV pixel buffer successfully, then still refuse decoder creation at-12913. Seventeen new terminal hosts include18exact software images; zero hardware images are claimed. [Start witnesses, context boundary and source](docs/VIDEO_NATIVE_START.md).

The native video factory now returns a verified non-null implementation. A same-executable AppleGVA board-policy experiment changes the hardware refusal from-12906 to-12913 in three cases; four negative controls preserve-12906. There are still zero hardware images. The19-host cohort includes30 exact software images and explicitly preserves20 nonzero internal FinF/Inva replies. [Factory, policy and next start-method boundary](docs/VIDEO_FACTORY_POLICY.md).

Native video transport now executes the pinned decoder callback inside our test process. Twenty-four software images through that transport match the CPU exactly; the full cohort has48images. The local hardware case still returns-12906, but now exposes the actual AppleGVA10.0.20 factory path. [Sources, preserved failures and next driver boundary](docs/VIDEO_LOCAL_SERVICE.md).

Video peer identity: 14 public PID/birth/path observations and two bounded log
windows corroborate the actual Intel decoder service. A pinned static native
path places the old selector in the `Strt` handler; its failing runtime branch
is still unproved. Thirteen new hosts include 18 exact software images, while
nine hardware creates still fail. [Evidence and next integration step](docs/VIDEO_PEER_IDENTITY.md).

Native video routing: three controlled presence cases reach the decoder service,
which replies `uber=0` then `Strt=-12906`; native and wrong-key controls have no
such observed exchanges. All hardware creates still fail. Nineteen terminal
host runs include 24 exact software images and bounded public-XPC forwarding
controls. [Evidence, source and limits](docs/VIDEO_ROUTING.md).

Native GPU dependency: a pinned public API confirms missing `IOGVACodec` on the GTX 880M. Three controlled presence substitutions change the GVA selection path, while native and wrong-key controls preserve the original path. All 13 new hardware creates still fail; 24 software images match the CPU exactly. [Evidence, scope and reproduction](docs/VIDEO_DEPENDENCIES.md).

Public-codec follow-up: H.264 and a new independent MPEG-2 fixture decode exactly in software, but nine hardware-required attempts still fail before images. The pinned model-policy site is not observed on our thread, so the availability result alone does not fix these paths. [Tests, source and next selection investigation](docs/VIDEO_CODEC_SELECTION.md).

Availability-query milestone: an exact-profile AppleVA query refuses the original model table but succeeds in three fresh processes when only our test process receives an `iMac11,1` entry. Seven native/wrong-model controls retain the refusal. This identifies an eligibility gate, not hardware decoding or a system fix. [Loaded providers, causal test and limits](docs/VIDEO_ELIGIBILITY.md).

Video investigation: the official NVIDIA WebVA has the same two stub factories as the examined support copy. Six iMac software-decoded images match an independent FFmpeg CPU reference exactly, but hardware-required VT still fails with zero images. Sources and a bounded own-process observer are now included; no hardware video or speedup is claimed. [Evidence and next transport work](docs/VIDEO_TRANSPORT.md).

An offline control analyzer now proposes reservations without applying them. Two exact NVIDIA programs pass 24 new GTX trials at manually selected settings, with 35,872 CPU-matching uint32 values. The 29-profile analysis does not certify hardware stack bounds or an automatic allocator; the runtime stays unchanged. [Evidence, source and reproduction](docs/NATIVE_CONTROL_PROPOSALS.md).

Latest native investigation: an explicit allocation API now shares the MRC import runtime, mutex and thread-local context. It preserves NVIDIA-generated code and passes228 GPU trials on17 native profiles, plus refusal, lifetime, CAS, local-memory and controlled factory-concurrency checks. A concurrency race in our CAS adapter is corrected. No installed-driver change or speedup is claimed. [Contract and limits](docs/NATIVE_ALLOCATION_API.md).

The unchanged API also passes new source-nesting104/120programs, with24additional lifetime trials on each common/public archive. Adjacent reservation settings distinguish failures from correct results in four native programs; a general allocator remains unproven. [Thresholds, source reproduction and evidence](docs/NATIVE_ALLOCATION_THRESHOLDS.md).

Read-only native command snapshots now map the local-memory and CRS fields on two profiles. A metadata reserve of4,096 produces a prepared CRS field of4,608; nine corrected trials pass while six native failures remain preserved. No packet patch/replay, resident-QMD readback or general allocator is claimed. [Field mapping and reproduction](docs/NATIVE_ALLOCATION_QMD.md).

New sequential blocks of 65 and 55 levels pass at a tested reserve of 2,560 while the fully nested program with 120 levels failed at 3,584. The segmented program contains more `joinat` instructions, so total counts do not explain the different sufficient reserves. Nine new trials pass and six numerical failures remain preserved; no automatic rule or VRAM saving is claimed. [Discriminating control shapes](docs/NATIVE_SEGMENTED_CONTROL.md).

## Included

- Objective-C++ runtime for native program import, targeted native CAS repair, native command handling, scoped ICB/argument encoders, and FP64 adapters.
- Readable MSL kernels, C/C++ compiler clients, CPU oracles, bounded GPU test harnesses, negative controls, and lifetime checks.
- Patches against pinned open source Mesa/NAK, OpenNVDA, and envytools revisions.
- Historical research and reproduction scripts, including developer examples. Some require locally regenerated fixtures; see [reproducibility](docs/REPRODUCIBILITY.md).
- A source manifest with original and published SHA-256 hashes. Four files received path/launcher portability edits; runtime sources match the qualified source snapshots.

## First steps

```sh
git clone https://github.com/ntn1007/KeplerMetal.git
cd KeplerMetal
python3 tools/check_publication.py
python3 -m unittest discover -s tests -v
```

On macOS with Xcode and the Metal toolchain selected:

```sh
python3 tools/build_from_source.py --out build/source-local
python3 tools/inventory_local_driver.py
```

The build compiles and links the runtime from text sources. It performs **no GPU dispatch** and does not require a driver binary in this checkout. Inventory reads installed components and prints version/hash information; it copies no component.

## What has been demonstrated?

Local experiments have executed native and NAK-produced code on the reference GTX, compared output with CPU oracles, repaired a specific native CAS result defect, and implemented selected command/resource paths for adapted applications. An earlier device argument-encoder milestone covered 192 selected cases. The subsequent function-encoder route passed 64 cases, and its three-pointer layout passed 60 cases on that library.

The latest extension connects three ordinary library constructors and five native function factories after **one explicit library registration**. It preserves native functions, metadata, descriptor aliases and existing pipeline/queue behavior. The reception client makes zero manual per-function registration or compute-adaptation calls. Qualification covered **296 GTX trials**, 31,583,232 exact uint32 values, 7,895,808 counted consumer invocations and 386,434,048 guard bytes. CPU observations comprise 20 native factory observations, 82 library contract cases, 98 lifecycle/contract cases and 93 legacy contract cases. Twelve same-source native M1 trials produced 156 matching common result files. [API contract](docs/NATIVE_FUNCTION_PIPELINES.md) · [Validation summary](docs/library-function-validation.json).

Explicit scope activation and one pinned library/program-set registration remain required. This qualifies six source functions, not arbitrary application shaders. Other queues and buffers created before activation are not automatically adapted. The separate public seven-object rebuild passed four GPU smoke trials; its full 296-trial suite was NOT RUN. This remains application integration level 2, with no new performance benchmark.

These observations are scoped to their binaries, profiles, and workloads. The public export is not itself a rerun of those experiments. Full hardware coverage, transparent integration into ordinary applications, and a generally modernized installed driver remain open. No general performance improvement is claimed. Details: [status](docs/STATUS.md).

## Local memory and compiler spills

The native driver already executes private/thread arrays and compiler spills. The new opt-in program-import path preserves its local-memory allocation while supplying the qualified structured-control reservation. The local-memory cohort passed **180 compute trials and 48 missing-dispatch controls**, covering 1–1,024 threads/group, private arrays up to 4 KiB/thread and actual NAK register spills. The CPU oracle checked 269,040 exact uint32 outputs with witnesses for 67,260 kernel invocations. CAS and ordinary-library regressions passed after the new import. This is a bounded backend/resource-ABI extension; no installed driver or Metal family is changed. [Contract and reproduction](docs/LOCAL_MEMORY.md) · [Validation](docs/local-memory-validation.json).

## Proprietary dependencies

**No Apple/NVIDIA driver, firmware, VBIOS, SDK, installer, compiled GPU program, or binary capture is included.** Obtain proprietary components separately from their publishers or your existing licensed installation. NVIDIA reference packages have official URLs and recorded checksums in [the dependency manifest](dependencies/references.json); [the dependency guide](docs/DEPENDENCIES.md) explains recovery and local-only extraction.

Open source dependencies are referenced at fixed revisions; their upstream notices are preserved in [third-party notices](THIRD_PARTY_NOTICES.md). This project's MIT license does not relicense any external dependency.

Contributions are welcome: independent reproductions, smaller valid test cases, CPU oracles, portability fixes, and evidence-backed driver/API work. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before changing a hardware profile.

The local-memory path also accepts the same MSL/AIR programs, with native-versus-AIR/NAK byte comparisons and explicit resource-layout rejection controls. [Frontend contract and reproduction](docs/AIR_LOCAL_MEMORY.md).

Deep-control work has a mixed result: external-CRS imports up to2KiB pass their bounded tests, while a native96-level case fails after an observed entry write. The failure is retained and the full goal remains incomplete. [Control-flow investigation](docs/CONTROL_FLOW.md).

For a narrowly scoped, opt-in standalone public-Metal client experiment and its controls, see [the standalone ICB experiment](docs/STANDALONE_ICB_EXPERIMENT.md).
