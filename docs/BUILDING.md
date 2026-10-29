# Build from source

[VIDEO_VT_CVMETAL.md](VIDEO_VT_CVMETAL.md) documents the H.264 software-decode to GTX Metal NV12 witness.

[VIDEO_CVMETAL_NV12.md](VIDEO_CVMETAL_NV12.md) documents the Core Video/Metal NV12 witness and reproduction.

[APPLE_APPLICATION_ICB.md](APPLE_APPLICATION_ICB.md) documents the local Apple sample application witness and reproduction.

[APPLE_AUTOMATIC_STORYBOARD.md](APPLE_AUTOMATIC_STORYBOARD.md) documents automatic encoder adaptation in the Apple storyboard and its reproduction.

[APPLE_CACHE_BENCHMARK.md](APPLE_CACHE_BENCHMARK.md) documents the paired encoding benchmark and reproducible controls.

[APPLE_INHERITED_CACHE.md](APPLE_INHERITED_CACHE.md) documents the scoped inherited-record cache and reproduction.

[APPLE_STORYBOARD_INFLIGHT.md](APPLE_STORYBOARD_INFLIGHT.md) documents the queued-frame witness and reproduction.

[APPLE_STORYBOARD_ICB.md](APPLE_STORYBOARD_ICB.md) documents the storyboard/controller ICB witness and reproduction.

[APPLE_DEPTH_DONTCARE.md](APPLE_DEPTH_DONTCARE.md) documents the scoped depth-store extension and reproduction.

[APPLE_REAL_RENDERER.md](APPLE_REAL_RENDERER.md) documents the locally adapted Apple renderer comparison and reproduction.

[APPLE_MTKVIEW_ICB.md](APPLE_MTKVIEW_ICB.md) documents the MTKView delegate ICB depth witness and reproduction.

[APPLE_WINDOW_ICB.md](APPLE_WINDOW_ICB.md) documents the window-attached ICB depth witness and serialized reproduction.

[VIDEO_RM_USER_OPEN.md](VIDEO_RM_USER_OPEN.md) documents the bounded unprivileged port observation and refusal controls.

[VIDEO_RM_CURRENT_PROFILE.md](VIDEO_RM_CURRENT_PROFILE.md) documents the signed, no-open current-profile observation and captured controls.

[VIDEO_RM_DEVICE_IDENTITY.md](VIDEO_RM_DEVICE_IDENTITY.md) documents the device allocation comparison and read-only PCI observation.

[VIDEO_RM_NESTED_CLASSLIST.md](VIDEO_RM_NESTED_CLASSLIST.md) documents the offline class-list handler and nested-buffer audit.

[VIDEO_RM_CONTROL_PATH.md](VIDEO_RM_CONTROL_PATH.md) documents the offline RM control path audit and its retained evidence requirements.

[UNCOMMITTED_REVOKE.md](UNCOMMITTED_REVOKE.md) documents the isolated revocation witness and pinned re-audit.

[VIDEO_SELECTOR_PATH.md](VIDEO_SELECTOR_PATH.md) documents the bounded on-disk synchronous dispatch audit and model tests.

[VIDEO_CHANNEL_BRANCHES.md](VIDEO_CHANNEL_BRANCHES.md) describes the read-only three-profile direct call and jump audit.

[VIDEO_HIGH_SIERRA_COMPARISON.md](VIDEO_HIGH_SIERRA_COMPARISON.md) documents signed historical components, offline extraction and the pinned comparison.

[VIDEO_LEASE_PENDING_GPU.md](VIDEO_LEASE_PENDING_GPU.md) describes the submitted-command lifecycle cohort and verifier tests.

[VIDEO_GUARDED_BACKEND.md](VIDEO_GUARDED_BACKEND.md) documents the experimental reusable backend, CPU tests and pinned GPU cohort.

[VIDEO_SHARED_LEASE_GPU.md](VIDEO_SHARED_LEASE_GPU.md) documents the bounded associated video-lease release cohort and audit.

[VIDEO_SHARED_REFERENCE_GUARD.md](VIDEO_SHARED_REFERENCE_GUARD.md) describes the bounded alias reference-release GPU cohort and re-audit.

[VIDEO_SHARED_CLOSE_TIMING.md](VIDEO_SHARED_CLOSE_TIMING.md) documents the delayed-close comparison and its audit.

[VIDEO_SHARED_ISOLATION.md](VIDEO_SHARED_ISOLATION.md) documents the type-6-only isolation and failure audit.

[VIDEO_CONTEXT_COMPUTE.md](VIDEO_CONTEXT_COMPUTE.md) documents the post-association Metal queue failure and raw-output audit.

[VIDEO_CONTEXT_LEASE.md](VIDEO_CONTEXT_LEASE.md) documents the optional video context lifecycle component and tests.

[VIDEO_PROVIDER_ASSOCIATION.md](VIDEO_PROVIDER_ASSOCIATION.md) documents selected-service association and its pinned re-audit.

[VIDEO_PROVIDER_CONTEXT.md](VIDEO_PROVIDER_CONTEXT.md) documents the selected-service context open/close and controls.

[VIDEO_PROVIDER_SERVICE.md](VIDEO_PROVIDER_SERVICE.md) documents the selected legacy service observation and pinned re-audit.

[VIDEO_PROVIDER_FIELDS.md](VIDEO_PROVIDER_FIELDS.md) documents the re-audit of historical caller fields and existing controls.

[VIDEO_PROVIDER_REGISTRATION.md](VIDEO_PROVIDER_REGISTRATION.md) documents historical registration bounds and its offline model.

[VIDEO_GVA_PROPERTY.md](VIDEO_GVA_PROPERTY.md) documents the scoped property observer, calibration safety and static branch audit.

[VIDEO_GVA_OFFLINE_FLAG.md](VIDEO_GVA_OFFLINE_FLAG.md) documents the single-key comparison and IOKit iterator observation.

[VIDEO_GVA_SUPPORT_OVERLAY.md](VIDEO_GVA_SUPPORT_OVERLAY.md) documents the scoped support-table counterfactual and unchanged-return registry observation.

[VIDEO_GVA_BOARD_OBSERVATION.md](VIDEO_GVA_BOARD_OBSERVATION.md) documents the pinned board-read observer and controls.

[VIDEO_GVA_SELECTION_STATIC.md](VIDEO_GVA_SELECTION_STATIC.md) documents the read-only candidate-selection audit.

[STANDALONE_MULTI_COPY.md](STANDALONE_MULTI_COPY.md) documents the bounded two-copy experiment and reproduction.

[STANDALONE_COPY_POLICY.md](STANDALONE_COPY_POLICY.md) documents the scoped client policy and GPU-copy qualification.

[STANDALONE_AUTOMATIC_COPY.md](STANDALONE_AUTOMATIC_COPY.md) covers object-based scoped GPU ICB copying and preflight.

[STANDALONE_PARTIAL_COPY.md](STANDALONE_PARTIAL_COPY.md) documents the public-Metal scoped GPU-copy client and its controls.

[STANDALONE_PARTIAL_COMPUTE.md](STANDALONE_PARTIAL_COMPUTE.md) covers the public-Metal partial compute client and same-runtime regressions.

[PARTIAL_ICB_GPU_DUAL_COPY.md](PARTIAL_ICB_GPU_DUAL_COPY.md) documents the two-pipeline mixed-copy qualification. [PARTIAL_ICB_GPU_MIXED_COPY.md](PARTIAL_ICB_GPU_MIXED_COPY.md) covers the later mixed copy qualification. [PARTIAL_ICB_GPU_RANGE.md](PARTIAL_ICB_GPU_RANGE.md) documents the scoped GPU-timeline partial range copy and regressions. [PARTIAL_ICB_GPU_COPY.md](PARTIAL_ICB_GPU_COPY.md) retains the earlier single-command qualification. [PARTIAL_ICB_OVERLAP.md](PARTIAL_ICB_OVERLAP.md) documents the overlapping CPU snapshot cohort. [PARTIAL_ICB_SNAPSHOT.md](PARTIAL_ICB_SNAPSHOT.md) documents the preceding snapshot and same-runtime GPU regression. [CAS_REGISTER_SPAN.md](CAS_REGISTER_SPAN.md) documents the updated register check. [SEGMENTED_LIBRARY_CLIENT.md](SEGMENTED_LIBRARY_CLIENT.md) documents a separate client and three-segment library loading. [STANDALONE_DATA_CAS.md](STANDALONE_DATA_CAS.md) documents the preceding URL/data qualification. [STANDALONE_DYNAMIC_CAS.md](STANDALONE_DYNAMIC_CAS.md) documents the preceding process-local public-Metal client qualification. [CAS_DYNAMIC_SLOT.md](CAS_DYNAMIC_SLOT.md) covers the prior SDK qualification and [CAS_SLOT3.md](CAS_SLOT3.md) the fixed-slot test.

[CAS_BACKEDGE_SDK.md](CAS_BACKEDGE_SDK.md) documents the newly completed single-overlay CAS GPU qualification.

[CAS_BACKEDGE_SAFETY.md](CAS_BACKEDGE_SAFETY.md) gives the offline backedge counterexample and regression audit.

[VIDEO_ALLOCATION_CHAIN.md](VIDEO_ALLOCATION_CHAIN.md) documents the offline, hash-bound video-resource allocation audit.

[NOCOPY_OWNED_REGISTRATION.md](NOCOPY_OWNED_REGISTRATION.md) documents the owned completion gate, mock lifetime tests and GTX qualification.

[NOCOPY_METAL_REGISTRATION.md](NOCOPY_METAL_REGISTRATION.md) documents the Metal completion registrar, mock tests and GTX qualification.

[NOCOPY_WORK_REGISTRY.md](NOCOPY_WORK_REGISTRY.md) documents explicit work tracking, GPU evidence and CPU concurrency tests.

[NOCOPY_CLIENT_GUARD.md](NOCOPY_CLIENT_GUARD.md) documents an independent client block, a scoped guard and separate GPU/CPU checks.

[NOCOPY_CLIENT_BLOCK.md](NOCOPY_CLIENT_BLOCK.md) documents the client-owned block experiment and separate GPU/CPU checks.

[NOCOPY_CLIENT_CALLBACK.md](NOCOPY_CLIENT_CALLBACK.md) describes the separately compiled client, scoped GPU release and raw-output auditor.

[STANDALONE_CAS.md](STANDALONE_CAS.md) describes the explicitly injected, pinned public-Metal CAS client and its native/repair controls.

[CAS_SDK_REGENERATED.md](CAS_SDK_REGENERATED.md) describes the current native CAS SDK, pinned decoder, isolated preparation and GTX qualification.

[PARTIAL_ICB_DUAL_PIPELINE.md](PARTIAL_ICB_DUAL_PIPELINE.md) describes the pinned dual-shader build, construction-only inspection, serial GPU controls, regressions and independent CPU audit.

[COMBINED_INDEX_VERTEX.md](COMBINED_INDEX_VERTEX.md) documents source building, native inspection and a signed two-slot render probe.

[VERTEX_BINDING_EXPERIMENT.md](VERTEX_BINDING_EXPERIMENT.md) documents the owned vertex-transition context, construction-only compiler inspection and signed render reception.

[INDEXED_RENDER.md](INDEXED_RENDER.md) adds the indexed producer build, construction-only inspector/certifier and `--typed-indexed-render` reception. The complete runtime gains an optional owned index-binding extension while preserving the basic root prefix.

[TYPED_RENDER_DRAW.md](TYPED_RENDER_DRAW.md) adds a source-only typed draw/reset producer, its independent native MSL reference and inspection/certification gate. `--typed-render-draw` extends the render-argument builder; the combined auditor recomputes producer and rendered-image controls.

[RENDER_RECORD_ARGUMENTS.md](RENDER_RECORD_ARGUMENTS.md) adds `--render-argument-encoders` to the AIR render builder, owned context APIs, ordinary native PSO checks and separate 27-host reception / 16-host regression auditors. The fresh seven-object runtime changes its ICB object only.

[AIR_RESET_RENDER.md](AIR_RESET_RENDER.md) adds `--air-reset-build` plus `--air-reset-inspections` to the render catalogue builder. A separate MRC factory with C linkage verifies the previously certified program for the ARC host. The source-built runtime and materializer remain unchanged; seven opt-in modes qualify the final image and negative controls.

[AIR_RESET_DATAFLOW.md](AIR_RESET_DATAFLOW.md) adds structural command-root metadata recognition and the separate qualified typed producer, preserving its arithmetic, branches and ordinary buffer metadata. Its source-only builder, certificate gate and auditor reuse the preceding native capture/section parser without changing the core runtime.

[AIR_RENDER_RESET.md](AIR_RENDER_RESET.md) adds a source-only exact-profile AIR translator, construction/offline-certification gate, signed GPU reset/reference probes and portable auditor. It requires Xcode/Metal and local envytools, with no NAK or core runtime link. An unknown input profile refuses rather than silently changing pins.

[GPU_ICB_TEXTURE_ARGUMENTS.md](GPU_ICB_TEXTURE_ARGUMENTS.md) gives a complete public-source auxiliary-shader rebuild, a three-buffer native producer, GPU-side texture argument selection and the 28-host raw-evidence auditor. [ICB_TEXTURE_ARGUMENTS.md](ICB_TEXTURE_ARGUMENTS.md) supplies the preceding native/CPU-ICB reference cohort.

[NATIVE_SOURCE_LIBRARY_FACTORIES.md](NATIVE_SOURCE_LIBRARY_FACTORIES.md) adds `--library-factories`, ordinary native source library/function/PSO routes, zero-submission contracts, optional legacy-library references and a complete 94-host auditor.

[REUSABLE_ICB_CONTEXTS.md](REUSABLE_ICB_CONTEXTS.md) adds `--reusable-contexts`, an explicit generation-tagged source ABI, producer/materializer/consumer leases, CPU lifetime contracts and a 52-process reusable/regression auditor. Workspace-header builds disable compiler modules to avoid importing definitions from an earlier build directory.

[STABLE_PIPELINE_IDENTITIES.md](STABLE_PIPELINE_IDENTITIES.md) adds `--stable-identities`, a private extended context with unchanged executable record ABI, duplicate-template binding and retired-scope GPU controls.

[NATIVE_SOURCE_FUNCTION_ARGUMENTS.md](NATIVE_SOURCE_FUNCTION_ARGUMENTS.md) adds `--function-arguments` to the native producer workflow, with public function encoders, native pipeline factories, ownership/reuse tests and two legacy reference routes.

[NATIVE_MSL_COMMANDS.md](NATIVE_MSL_COMMANDS.md) gives the native source-lowered producer build, complete GPU record/dataflow matrix and prior-NAK comparison. Native-only builds need six existing native fixtures; archived NAK programs are optional. The builder generates workspace-only include/readonly-member adaptations and explicitly checks two compiler refusal cases.

[NATIVE_RESOURCE_IDENTITIES.md](NATIVE_RESOURCE_IDENTITIES.md) gives an Xcode-only source build, direct native texture/sampler GPU tests across three requested language standards, a construction-only ICB compiler diagnostic and a portable 41-process auditor. It uses no runtime archive or prebuilt shader fixtures.

[SHARED_GENERIC_IMPORT.md](SHARED_GENERIC_IMPORT.md) gives the fresh compute/vertex/fragment/tessellation reception builder and portable 39-host raw-output auditor. The C ABI facade now requires the complete seven-object archive; current `KeplerProgramImport.mm` alone is not a standalone dylib build. Historical frozen source/builds remain separate.

[ADAPTER_PROFILES.md](ADAPTER_PROFILES.md) describes the five-client reception builder for a new complete public archive and an existing locally generated 60-program asset SDK. It checks the original asset manifest, regenerates input recipes, freezes independent oracles and links clients without reusing old runtime objects. GPU qualification remains separate from source compilation.

The new [memory-accounting cohort](MEMORY_ACCOUNTING.md) requires extended builds of both separately pinned large/legacy carriers against the same runtime archive. The investigated signature-only driver variant has a separate bounded compute/CAS qualification; unknown profiles still refuse before host launch. [Exact profiles and PCI identity](DRIVER_PROFILES.md). Compilation is not GPU qualification.

The 8/16 KiB private local-memory import has a separate public seven-object archive qualification. [LARGE_LOCAL_MEMORY.md](LARGE_LOCAL_MEMORY.md) gives source-only program/carrier generation, strict profile checks, serialized GPU suites and the CAS coexistence prerequisites. These GPU tests are separate from the standard CPU-only build.

The optional `KeplerResidentBatch` ARC object is compiled separately from the original seven-object core. [NATIVE_RESIDENT_BATCH.md](NATIVE_RESIDENT_BATCH.md) provides the standalone text build, strict native profile, preparation/serial/segmented/parallel prerequisite chain and independent CPU auditor. Its GPU runs require the same existing common host reservation; the administrator video experiment is separate.

The bounded two-kernel resident-overlap client has a standalone text-only build, signed GPU runner and portable verifier. [NATIVE_RESIDENT_OVERLAP.md](NATIVE_RESIDENT_OVERLAP.md) gives the complete seven-object rebuild, separate serial qualification, guarded candidate run and common host reservation. It changes only its own validated uncommitted stream; it does not implement the ordinary concurrent encoder API or claim a speedup.

The unchanged public-API start/CV observers and bounded cache-target mapper are documented in [VIDEO_NATIVE_START.md](VIDEO_NATIVE_START.md). V8 source can reconstruct V5/V6/V7 using original-text patches; reconstruct V5 before applying older V5-to-V1/V2/V3/V4 patches. The new17-host auditor rechecks frozen results and performs no native execution.

The factory/policy observer reuses the qualified native transport without changing the common runtime. [VIDEO_FACTORY_POLICY.md](VIDEO_FACTORY_POLICY.md) gives inspect/software/original-policy/wrong-board controls before the current-board experiment, strict resident profiles, source-version reconstruction and the CPU-only historical auditor. Hardware creation remains refused; the changed status is not decoding qualification.

The anonymous native video experiment and independent public-XPC controls have separate, source-only laboratory builders. [VIDEO_LOCAL_SERVICE.md](VIDEO_LOCAL_SERVICE.md) gives strict profiles, fresh-directory commands, archived-source reconstruction and the four preserved qualification failures. The completed hardware presence test still produces zero images.

The schema3 routing observer adds public peer metadata and errno-preserving
forwarding. [VIDEO_PEER_IDENTITY.md](VIDEO_PEER_IDENTITY.md) documents controlled
on/off cases, archived-source reconstruction, bounded logs and static native
entry/selector mapping. No new hardware-video success is implied.

The public XPC observer preserves the existing codec implementation and observes
the next service refusal. [VIDEO_ROUTING.md](VIDEO_ROUTING.md) covers exact
caller identities, two logger source versions, bounded status decoding,
serialized reproduction and the independent historical auditor.

The public IORegistry observer and tightly scoped presence experiment reuse the qualified host, decoder and observation libraries. [VIDEO_DEPENDENCIES.md](VIDEO_DEPENDENCIES.md) documents inspect/software controls, the unchanged hardware requirement, rotated native/wrong-key/present-key cases and source-version reconstruction.

The public-codec client now accepts H.264 or an original MPEG-2 fixture, with an independent software-reference generator using existing external FFmpeg tools. [VIDEO_CODEC_SELECTION.md](VIDEO_CODEC_SELECTION.md) describes the exact-profile build, inspect-first workflow and retained hardware failures.

The dyld image catalogue and exact-profile AppleVA availability experiment are also separate from the common runtime archive. Their source-only builders and strict resident-code checks are documented in [VIDEO_ELIGIBILITY.md](VIDEO_ELIGIBILITY.md). Availability success does not qualify hardware decoding.

The video observer and reference stager are separate, process-local diagnostic tools; they do not change the runtime archive. [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md) lists their fixture requirements, serialized runs and CPU-only historical auditor. Building or completing a diagnostic does not qualify hardware video.

The new CPU-only control analyzer and its manually qualified native examples are documented in [NATIVE_CONTROL_PROPOSALS.md](NATIVE_CONTROL_PROPOSALS.md). Portable decoder/refusal tests run in the normal test suite. `audit_native_control_proposals.py --lab-root` rechecks historical fixtures without GPU dispatch. The analyzer changes no runtime allocation; the sweep verifier requires explicit `--variant reload_bounds` for that immutable-input nested oracle.

## Supported public build

Use macOS with the Xcode developer directory selected, an SDK containing Metal, clang++, ar, and Python 3.9 or later. The laboratory source baseline used SDK 26.2 / clang 17 on x86_64. Full Xcode plus its Metal toolchain is needed to regenerate MSL assets; install these using Apple's tools and terms.

```sh
python3 tools/check_publication.py
python3 -m unittest discover -s tests -v
python3 tools/build_from_source.py --out build/source-local
```

The builder requires a **new** directory beneath `build/`. It freezes text inputs, compiles all runtime objects, archives `libKeplerMetal.a`, builds a link-check client, and runs that CPU-only client. It does not reuse objects from `results/`, download anything, allocate a GPU resource, or submit a command buffer. It records commands, tool versions, source/object/library hashes, and logs in the output directory. The executable links the whole archive so unresolved optional-runtime symbols are detected.

Memory management is intentional: `KeplerProgramImport.mm` and `KeplerNativeCAS.mm` compile with `-fno-objc-arc`; the other runtime implementations use `-fobjc-arc`. C factory return ownership is declared in headers. The target is baseline x86_64; there is no `-march=native`.

The FP64 pin include allows source compilation without bundling any GPU code. It does not make FP64 usable without locally generated programs matching the pins.

## Historical reproduction scripts

The extensive `bridge/tools/` and `bridge/sdk*/examples/` scripts preserve the experiments' sources. Many later scripts intentionally depend on earlier frozen `build/` and `results/` directories. Those binary trees are **not** in this source release. Consequently, running a late milestone builder directly in a fresh checkout may fail with a missing prerequisite; the source-only build above is the standalone supported entry point.

For compiler experiments, obtain the pinned open source trees described in [dependencies](DEPENDENCIES.md), inspect and apply the corresponding patches, then follow the early `setup_tools.py`, `build_air_compiler.py`, `reproduce_nak_macos.py` and subsequent reproduction scripts. `setup_tools.py` is historical and expects an additional local Rust download manifest; it is not an automatic bootstrap for a clean checkout. Rust 1.99.0 and the package versions in `bridge/tools/python-requirements.txt` were recorded in the lab. Preserve dependency ABI versions when rebuilding. No complete clean-room regeneration of every milestone is claimed yet.

Late runtime builders that reuse earlier objects are retained for provenance. Do not confuse them with `tools/build_from_source.py`, which rebuilds every runtime object from the published text.

## GPU qualification

GPU execution is a separate, explicit operation. Native driver/private ABI profiles are narrowly pinned to the reference device and binaries. Read the relevant harness and negative controls before running. Use the common `bridge/tools/lab_gpu_reservation.py` protocol and the immutable signed launcher; never invoke multiple GPU cohorts concurrently.

The M1 comparison source programs are included. Private SSH transfer scripts are excluded: copy only the required source bundle using your own authorized connection, verify both-end hashes, and keep the reference run separate from GTX qualification. M1 inference or execution cannot validate SM30.

## Registered pipeline contract milestone

The public builder still rebuilds all seven runtime objects, including the changed MRC descriptor import transport. `examples/command_ir_pipeline_contracts.mm` and `examples/PipelineFactoryReception.inc` are the exact text of the six-factory reception client and helper; their hashes are in `SOURCE_SNAPSHOT.json`. Local builders under `bridge/tools/` preserve the frozen-asset dependencies and are not standalone fresh-checkout GPU launchers. See [the contract](NATIVE_FUNCTION_PIPELINES.md) for supported options, callbacks and descriptor limitations.

The thread-limit candidate additionally includes `KeplerNativeThreadLimits.inc`. The lab reception builder accepts `--thread-limit` and `--producer-threads`; these control different things. Example using existing frozen prerequisites: `--thread-limit 1024 --producer-threads 1024`. Invalid local sizes are tested without committing their command buffers. The standard public source build performs no GPU dispatch; separate artifact-specific GPU qualification is required.

For the ordinary-factory lab client, add `--automatic-encoders` to `bridge/tools/build_pipeline_contract_reception_client.py`. This removes manual compute-adaptation calls and includes `QueueFactoryReception.inc`; it still needs the frozen local assets described above. `qualify_pipeline_factory_contracts.py` covers the default queue/encoder route, and `qualify_ordinary_queue_factories.py` covers the other retained queue/compute factory combinations. `build_registered_pipeline_contract_probe.py --negatives` provides modes `automatic`, `automatic_lifetime`, `automatic_saved_imps`, `automatic_blocking` and `pending`. The blocking-pool control submits one empty command buffer and no user kernel; the other factory/lifetime controls submit none.

For one library registration followed by ordinary `MTLLibrary`/`MTLFunction` calls, also add `--library-registration`. The client includes `LibraryFunctionReception.inc`; a full selection is `5:1:4:2:6:barrier`. `qualify_pipeline_factory_contracts.py` and `qualify_library_function_factories.py` cover the pipeline and library/function matrices. Build CPU contract probes with `--negatives --library-registration`, using modes `library`, `library_lifetime` and `pending`. These probes create native objects and inspect contracts without submitting command buffers. The legacy probe without `--library-registration`, in mode `automatic`, retains a separate regression check. See [the bounded contract](NATIVE_FUNCTION_PIPELINES.md) before using these historical lab builders.

## Native local-memory reference and opt-in import

The native-only local-memory example can compile its MSL and host directly from published text, then run the qualified native driver. See [LOCAL_MEMORY.md](LOCAL_MEMORY.md) for commands, device/profile guards and how to share an existing reservation root across checkouts. It submits GPU work explicitly and stays separate from the CPU-only source build.

The opt-in local-memory API is supplied by the shared MRC `KeplerNativeCAS` object in the complete archive. The legacy standalone program-import implementation does not provide this new symbol. Imported local/spill programs still require qualified, pinned carrier/program assets; no clean-checkout regeneration of the complete import cohort is claimed.

The same MRC object now supplies `KeplerNativeAllocation.h`: the explicit, pinned allocation correction shares its import mutex and uses a thread-local scope. The public builder includes its header/implementation from text. See [NATIVE_ALLOCATION_API.md](NATIVE_ALLOCATION_API.md) for ownership, refusal behavior, concurrency scope and frozen-fixture reproduction. A source build alone does not qualify the new GPU path.

The offline envytools wrapper `bridge/tools/envydis-build/CMakeLists.txt` is now published. [NATIVE_ALLOCATION_THRESHOLDS.md](NATIVE_ALLOCATION_THRESHOLDS.md) gives its source-only configuration and a native104/120generation/observation/reservation workflow. The native examples can be regenerated from text; no compiled driver or shader is distributed. The aggregate milestone auditor still requires the named frozen lab fixtures.

The native QMD capture builder has an explicit `--execute` option; its default host only captures uncommitted commands. Both hosts use existing frozen assets and a qualified archive. The decoder and execution verifier accept `--reservation-root` for an existing shared laboratory lease; the CPU-only suite accepts `--lab-root` to audit that tree from another checkout. No private root is inferred or silently substituted. [Commands, field mapping and limits](NATIVE_ALLOCATION_QMD.md).

`bridge/tools/native_segmented_control.py native` generates the bounded48+48and65+55MSL programs and the native observer from text. Its `client` phase generates certificates from the resulting native observations and links the unchanged common archive; standalone2,048/2,560uses the pinned experimental factory, common4,096uses the shared API. All builds perform zero GPU dispatch. Both phases accept explicit `--lab-root` for an existing laboratory tree. Numerical tests are portable; the historical aggregate auditor still requires omitted local fixtures. [Commands and evidence boundaries](NATIVE_SEGMENTED_CONTROL.md).

The scoped GPU render-range extension has a source-only client builder, pinned native materializer and a separate GPU/CPU raster qualification. [GPU_RENDER_EXECUTION_RANGES.md](GPU_RENDER_EXECUTION_RANGES.md) gives the explicit prepass contract, lifecycle/refusal controls and serialized reproduction commands.

[GPU_RENDER_COMMAND_RECORDS.md](GPU_RENDER_COMMAND_RECORDS.md) adds scalar draw-record generation/validation, a complete 48-source runtime manifest, nonempty drained-pool lifetime controls and the 42-process reception auditor. The source-only client builder now also accepts the record modes.

[GPU_RENDER_STATE_CATALOGUE.md](GPU_RENDER_STATE_CATALOGUE.md) adds immutable render-state candidates, opaque identities, GPU draw predicates, separate pipeline/resource controls and a 54-process auditor. The launcher runs its frozen oracle in an isolated interpreter and records validation separately from native execution.

[NATIVE_RENDER_SOURCE_COMMANDS.md](NATIVE_RENDER_SOURCE_COMMANDS.md) adds `--source-commands` to the catalogue client builder, an explicit MSL render-command header, native shader compilation and a twelve-mode raw-record-equivalence auditor. The default raw-record producer remains available.

[NATIVE_COMMAND_COMPILER_BOUNDARY.md](NATIVE_COMMAND_COMPILER_BOUNDARY.md) provides standalone construction-only typed/raw command probes, optional process-local MRC capture, frozen AIR text and a strict observation auditor. No diagnostic kernel is dispatched.

[NATIVE_COMMAND_BINDING_READBACK.md](NATIVE_COMMAND_BINDING_READBACK.md) adds owned private-code range validation, guarded blit-only readback, uncommitted compute/QMD snapshots and missing-copy controls. The host has no compute-CB submission mode.

The [descriptor CAS experiment](DESCRIPTOR_CAS.md) requires the separately qualified local SDK and lab reservation; it is not a clean-checkout GPU build.
