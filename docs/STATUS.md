# Status, 2026-10-29

The retained High Sierra update has no `IOGVACodec` key in 15 inspected GeForce/NVDA plists and no literal in 19 selected binaries; dynamic or other producers remain unexcluded. [Evidence](VIDEO_GVA_HIGH_SIERRA_INVENTORY.md).

The pinned AppleGVA non-null codec-property path calls `CFStringGetCString` with a 32-byte ASCII buffer; the inspected Apple and NVIDIA plists do not identify a Kepler value. [Evidence](VIDEO_GVA_CODEC_CONTRACT.md).

Two scoped video processes correlate a null AppleGVA `IOGVACodec` return and zero node byte with the same later list-head address. Allocation lifetime and hardware decoding remain unproved. [Evidence](VIDEO_GVA_PROPERTY_NODE_LINK.md).

Two scoped video processes have a one-entry AppleGVA list with filter byte `0x463` equal to zero; pinned code would skip that entry under the observed selection mode if it remains unchanged. The byte's meaning and hardware decode remain unknown. [Evidence](VIDEO_GVA_LIST_FILTER.md).

Two scoped AppleGVA video requests return an observed zero list length from the routine immediately after the constructor; entry semantics and the cause of the empty list remain unknown. [Evidence](VIDEO_GVA_ENUMERATION_RESULT.md).

Two scoped AppleGVA processes reach both instructions following the base and derived constructor calls, with same-thread selector-2 and matching caller frames. Hardware video still returns -12913. [Evidence](VIDEO_GVA_CONSTRUCTOR_RETURN.md).

A CPU-only dynamic-loading calibration observes two hardware breakpoints, rejects a wrong base, and verifies the target bytes at both hits. [Evidence](VIDEO_GVA_HW_WITNESS.md).

Two scoped AppleGVA video requests produce no events at a conditional post-constructor deallocator callsite; constructor completion and hardware decode remain unproved. [Evidence](VIDEO_GVA_POSTCONSTRUCTOR.md).

A historical AppleGVA stack correlates with one base-constructor branch under explicit pinned-code and entry-flow assumptions; neither the compared value nor the constructor return was observed. [Evidence](VIDEO_GVA_RTTI.md#base-constructor-branch-and-historical-stack).

Static RTTI identifies the constructor associated with the observed AppleGVA selector-2 branch as `Flow_QT0`, derived from `Flow`. Live object contents and constructor completion remain unproved. [Evidence](VIDEO_GVA_RTTI.md).

A process-local allocator observer records AppleGVA constructor register value 2 in three H.264 counterfactual runs. Decoder creation still fails with zero hardware images; the selector's meaning remains unknown. [Evidence](VIDEO_GVA_REGISTER.md).

Offline correlation narrows one previously recorded AppleGVA constructor branch to selector candidates 2 or 9 under explicit pinned-code/stack assumptions; the actual register and hardware video remain unobserved. [Evidence](VIDEO_GVA_DISPATCH.md).

The scoped CPU render ICB now treats selected zero-count and zero-instance triangle draws as inert. Two GTX direct/adapted process pairs match raw pixels; three invalid inputs remain refused. M1 direct/ICB references agree on the tested outcomes. [Evidence and limits](EMPTY_RENDER_DRAWS.md).

Two GTX cohorts correlate the relocated indirect-branch register byte and `0x330` entry within the same instrumented CAS shader. The exact source of entry and general control flow remain unproved. [Evidence](CAS_JOINT_WITNESS.md).

Three process-local GPU probes preserve the original indirect instruction and mark entry at candidate locations. The `0x330` control also marks a non-indirect-observed pattern, so marker origin remains unproved. [Evidence](CAS_TARGET_ENTRY_WITNESS.md).

Two GPU witness cohorts record the low byte of a relocated conditional CAS indirect-branch register for patterns 0, 2, 3 and 4, with native output controls. Actual destination entry and the unmodified branch remain unproved. [Evidence](CAS_BRANCH_REGISTER_WITNESS.md).

Two isolated GPU CB0 witnesses each read the three pinned candidate-section words across 99 threads; two known-value controls pass. This is a modified laboratory shader and does not trace the indirect branch. [Evidence](CAS_CB0_GPU_WITNESS.md).

Four unsubmitted native/repaired conditional CAS command captures each show a 256-byte CB0 at the variant's aligned code end. These captures did not read CB0 contents or trace the branch. [Evidence](CAS_CONDITIONAL_CB0.md).

The conditional CAS SDK checks the exact live auxiliary section before program substitution. GPU regression and a wrong-expected-digest constructor control passed; live `c0` binding and indirect-branch semantics remain unproved. [Evidence](CAS_CONDITIONAL_AUX_GUARD.md).

The conditional CAS capture has a three-word candidate indirect-branch table; its live constant-bank binding and branch semantics remain unproved. [Evidence](CAS_INDIRECT_BRANCH.md).

An offline explicit-use inspection finds four uses of the conditional CAS expected pointer and two uses of its bitcast, limited to lifetime markers, in the pinned AIR dump. Hidden/incorrectly decoded aliases and native SASS remain unqualified. [Evidence](CAS_CONDITIONAL_AIR_CFG.md#explicit-expected-pointer-uses).

An offline SSA trace follows the conditional CAS PHI through four vector insertions to a device-space store, with selected dominance checks. Alias safety, reachability on every path and native SASS flow remain unproved; no repair is authorized. [Evidence](CAS_CONDITIONAL_AIR_CFG.md#output-path-follow-up).

An offline AIR CFG observation recovers branch and PHI predecessor IDs for the conditional CAS, identifying its merge with the initialized value. The observation does not authorize repair, establish full dataflow or resolve the native indirect branch. [Evidence](CAS_CONDITIONAL_AIR_CFG.md).

The experimental CAS SDK now accepts the exact conditional profile only with pinned library, native code, replacement and metadata. Two GPU cohorts each validate 56,904 active operations and five pre-constructor refusals; earlier SDK profiles pass regression. The general AIR and SASS recognizers still refuse this shader; ordinary applications are not transparently fixed. [Evidence](CAS_DIVERGENCE_SDK.md).

An exact captured conditional-CAS program is corrected inside an adapted process. Two GPU cohorts each check 56,904 active operations and 455,040 output words; native/replay/NOP controls retain the defect. This is not general recognition or a system compiler repair. [Evidence](CAS_DIVERGENCE_REPAIR.md).

Conditional per-thread CAS results were compared on the GTX and an M1 Max reference. Two GTX runs reproduce 14,226 wrong active-thread expected values each while inactive values and other fields match; the M1 reference matches all checked fields. The separately captured NVIDIA output contains an indirect branch and the AIR contract refuses this shape. No new runtime repair is claimed. [Evidence](CAS_DIVERGENCE_REFERENCE.md).

An offline must-alias analysis follows copied CAS lock results across a bounded direct-branch graph. Seven synthetic decoded counterexamples are refused, but reconvergence entry remains assumed; no certificate or new GPU execution is authorized. [Evidence](CAS_LIVE_COPY_FLOW.md).

The application-local CAS SDK accepts the exact GPU-qualified copied-lock profile through its certified pipeline API. Seven GTX clients checked 22,482 operations through 1,024 threads per group and four changed inputs were refused before the constructor; a second cohort and the earlier four candidate profiles passed regression. General recognition and transparent integration remain open. [Evidence](CAS_LIVE_COPY_SDK.md).

A pinned native weak-CAS shader whose lock result moves between registers was repaired in a process-local experiment: six corrected GTX hosts checked 4,347 operations, and native/NOP/replay controls retained 2,619 wrong expected-value words. This is not general recognizer or SDK support. [Evidence](CAS_LIVE_COPY_EXPERIMENT.md).

The offline CAS recognizer now accounts for register writes in instructions combined with `join`. A synthetic one-instruction counterexample is rejected; the five archived diagnoses retain their verdicts. No synthetic code was dispatched and prior certificates are not automatically requalified. [Evidence and limits](CAS_JOIN_WRITE.md).

Two bounded UID 501 opens of the selected NVIDIA port returned `kIOReturnUnsupported` without a connection; the cause and current administrator behavior remain unproved. [Evidence](VIDEO_RM_USER_OPEN.md).

Four signed no-open profile controls identify the current `NVDA,Display-A` service while refusing the four-way PCI-only ambiguity; the historical privileged witness remains unqualified. [Evidence](VIDEO_RM_CURRENT_PROFILE.md).

The on-disk NVIDIA device-allocation paths and a 56-byte parameter layout were compared; two GTX PCI registry observations report board value zero. User-mode RM allocation and the loaded route remain unqualified. [Evidence](VIDEO_RM_DEVICE_IDENTITY.md).

The pinned NVIDIA RM control table links `0x800201` to a nested-buffer preparation/copy path; actual user-route reachability and valid handles remain unproved. [Evidence](VIDEO_RM_NESTED_CLASSLIST.md).

An offline audit relates the historical macOS RM control envelope to the installed NVIDIA dispatcher's distinct user and kernel paths. Class-list pointer marshalling and live access remain unqualified. [Evidence](VIDEO_RM_CONTROL_PATH.md).

The pinned NVIDIA macOS initializer obtains its candidate class list through two static `_NvRmControl` callsites with command `0x800201`; a later public NVIDIA definition has matching two-phase layout. Live classes and user-mode transport remain unverified. [Evidence](VIDEO_CLASSLIST_PROVENANCE.md).

Nouveau's GK104 decoder classes also appear in the pinned on-disk macOS NVIDIA class-selection and video-object paths. Current registry properties remain ambiguous between two candidates; live selection, channel access and hardware decoding remain unproved. [Evidence](VIDEO_NOUVEAU_CLASS_COMPARISON.md).

An experimental cooperative API abandons an exclusive, unsubmitted reusable producer and validates subsequent real ICB generations. General cancellation and transparent integration remain unimplemented. [Evidence and limitations](REUSABLE_ABANDON_API.md).

A real reusable ICB plan retains its producer independently of the lease: a lease-only abandonment pilot is refused. Two earlier isolated witnesses manually clear both states after instance revocation and validate four GPU generations each; their test-only mutation is superseded by the experimental API above. [Evidence and limitations](REUSABLE_PLAN_REVOKE.md).

Two actual reusable-lease instances tracking one native command buffer were tested with explicit test-only revocation and manual pending removal; this did not implement ICB cancellation. [Evidence and limitations](REUSABLE_REVOKE_WITNESS.md).

A process-local witness blocks ordinary commit/enqueue on one uncommitted Metal buffer and verifies subsequent GTX reuse; this alone did not implement reusable-ICB cancellation. [Evidence and limitations](UNCOMMITTED_REVOKE.md).

A pinned on-disk kernel and IOAccelerator audit predicts an Unsupported result for selector 0x105 only under specified synchronous-path assumptions; no live selector is tested. [Evidence](VIDEO_SELECTOR_PATH.md).

A three-profile static channel audit adds tail-jump coverage and shows the historical direct video-context route versus the bounded modern branch inventory; live reachability remains unknown. [Evidence](VIDEO_CHANNEL_BRANCHES.md).

A signed High Sierra 10.13.6 update contains the same return-14 NVIDIA video factory stub as the current profile; its on-disk video lookup is also inherited. This is static evidence, not hardware decode. [Comparison](VIDEO_HIGH_SIERRA_COMPARISON.md).

A gated Metal command remains submitted across a guarded experimental video-lease lifecycle and later completes correctly in two GTX trials. Execution concurrent with teardown remains unproved. [Evidence](VIDEO_LEASE_PENDING_GPU.md).

A reusable experimental guarded backend now rejects additional lifecycle failures; CPU mock and bounded GTX tests pass. Shared synchronization remains a caller responsibility. [Evidence and limitations](VIDEO_GUARDED_BACKEND.md).

A pinned experimental backend now combines the existing video lease, an associated type-3 context and guarded type-6 reference release; two later GTX compute runs pass while explicit-close controls fail. [Evidence and limits](VIDEO_SHARED_LEASE_GPU.md).

A guarded, process-local extra shared-client reference release preserves a new Metal queue and GPU compute in two GTX trials; the existing video lease remains unqualified. [Evidence and limits](VIDEO_SHARED_REFERENCE_GUARD.md).

**FAIL:** two delayed-close trials create Metal queues while an extra type-6 connection is open and receive nil after it closes; internal ownership remains unresolved. [Evidence](VIDEO_SHARED_CLOSE_TIMING.md).

**FAIL:** opening and closing an extra type-6 shared client alone reproduces the later Metal queue failure in two controlled processes; a video context or association is not necessary in this setup. [Evidence](VIDEO_SHARED_ISOLATION.md).

**FAIL:** new Metal queue creation returned nil in four post-association/teardown trials; no-context and context-only controls succeeded. Do not treat the experimental associated lease as qualified for continued Metal use. [Evidence](VIDEO_CONTEXT_COMPUTE.md).

A reusable experimental C++ lease manages the selected video context and shared-client lifecycle; two GTX associations and CPU failure-path tests pass, while video decoding remains unproved. [Evidence](VIDEO_CONTEXT_LEASE.md).

Two controlled legacy AppleGVA calls associate a newly opened type-3 video context with a new type-6 shared client on the selected GTX service; hardware video and provider integration remain unproved. [Evidence](VIDEO_PROVIDER_ASSOCIATION.md).

Two controlled legacy calls open and close a type-3 context on AppleGVA's selected GTX service; no legacy provider call, selector dispatch or hardware video is established. [Evidence](VIDEO_PROVIDER_CONTEXT.md).

Two controlled legacy AppleGVA calls select the GTX `nvAccelerator` service by its public registry ID. Sierra provider execution, compatible selector dispatch and hardware video remain unproved. [Evidence](VIDEO_PROVIDER_SERVICE.md).

An independent re-audit recovers two archived observations of legacy AppleGVA provider inputs: index 0, mask 15 and a nonzero selected entry. The full array and provider/kernel compatibility remain unqualified. [Evidence](VIDEO_PROVIDER_FIELDS.md).

A pinned historical NVIDIA video provider copies an input array through the highest set mask bit and checks a selected nonzero entry; a conservative offline model covers sparse masks. This does not establish the real caller, ABI compatibility or hardware decoding. [Evidence](VIDEO_PROVIDER_REGISTRATION.md).

Nine scoped AppleGVA processes read the NVIDIA accelerator properties; `IOGVACodec` was absent in each, and hardware-required decoding still produced no images. The pinned null branch and observer calibration have bounded evidence; the complete failure cause remains open. [Evidence](VIDEO_GVA_PROPERTY.md).

Removing one offline-renderer flag from a scoped AppleGVA donor suppresses the associated iGPU logs in three trials but does not enable hardware video. [Evidence](VIDEO_GVA_OFFLINE_FLAG.md).

A bounded AppleGVA support-table counterfactual changes the observed route but still returns -12913 with zero hardware images; the NVIDIA provider path remains unresolved. [Evidence](VIDEO_GVA_SUPPORT_OVERLAY.md).

AppleGVA read this iMac board ID in three process-local hardware requests; all still returned -12913 with zero images. Selection cause remains unknown. [Evidence](VIDEO_GVA_BOARD_OBSERVATION.md).

A static AppleGVA follow-up identifies three board comparisons and a conditional candidate-pointer fallback; the actual runtime selection and hardware decoder remain unresolved. [Evidence](VIDEO_GVA_SELECTION_STATIC.md).

Eight new GTX processes validate two disjoint ICB copies per encoder for the pinned profiles; this is opt-in and not general ICB support. [Evidence](STANDALONE_MULTI_COPY.md).

An explicit local policy selects two related public-Metal copy test clients using one signed bootstrap; third-party compatibility remains unqualified. [Evidence](STANDALONE_COPY_POLICY.md).

A pinned public-Metal client performs object-based, unlabelled GPU ICB copies with whole-range preflight. Third-party applications remain unqualified. [Evidence](STANDALONE_AUTOMATIC_COPY.md).

A pinned public-Metal client performs a labelled, scoped GPU copy of a mixed compute ICB; third-party applications remain unqualified. [Evidence](STANDALONE_PARTIAL_COPY.md).

A pinned public-Metal client executes a bounded dual-pipeline compute ICB through an explicit process-local bootstrap; ordinary applications remain unqualified. [Evidence](STANDALONE_PARTIAL_COMPUTE.md).

The opt-in project ICB path supports bounded GPU-timeline copies of prepared mixed partial and uniform ranges, including a qualified two-pipeline sequence on the scope queue. [Evidence](PARTIAL_ICB_GPU_DUAL_COPY.md). CPU snapshot overlap qualification remains [here](PARTIAL_ICB_OVERLAP.md); broader GPU copies remain unqualified. The native CAS vector-register check remains qualified [here](CAS_REGISTER_SPAN.md); arbitrary applications and shaders remain unqualified.

The single-overlay CAS SDK was regenerated using the backedge check and validated on the GTX; scope remains four adapted-client shader shapes. [Evidence](CAS_BACKEDGE_SDK.md).

The offline CAS diagnosis now rejects post-redirect backedges that can revisit earlier code. Existing policies require regeneration. [Evidence](CAS_BACKEDGE_SAFETY.md).

A static video allocation audit identifies the NVIDIA `nvTextureBuffer` factory and conditional memory paths; no live allocation or decoding is established. [Evidence](VIDEO_ALLOCATION_CHAIN.md).

Pending registered Metal completions now retain their registry gate; untracked work and general application integration remain open. [Evidence](NOCOPY_OWNED_REGISTRATION.md).

A scoped registrar attaches completion handlers to explicitly registered Metal command buffers; omitted work remains undetected. [Evidence](NOCOPY_METAL_REGISTRATION.md).

A scoped no-copy guard tracks explicitly registered command completions and GPU output validation. Unknown work is not detected. [Evidence](NOCOPY_WORK_REGISTRY.md).

A guarded no-copy prototype now invokes a retained, independent client block after two explicitly verified GTX commands; unknown workloads remain unqualified. [Evidence](NOCOPY_CLIENT_GUARD.md).

A separately compiled test client supplies the actual no-copy block; a gated process-local action invokes it after two verified GTX commands. [Evidence and limits](NOCOPY_CLIENT_BLOCK.md).

A separately compiled test client supplies the callback for a guarded no-copy release after two verified GTX commands; arbitrary application callbacks remain unqualified. [Evidence](NOCOPY_CLIENT_CALLBACK.md).

A guarded test-only no-copy callback returned its own Mach VM allocation after two verified GTX commands in three cases; other applications and general resource lifetime remain unqualified. [Evidence and reproduction](NOCOPY_RELEASE_WITNESS.md).

A scoped launcher now starts a selected allowlisted client under the shared GPU reservation, after checking the exact profile and signed artifacts. Six GTX client processes reproduce the native defect and validate 142,200 repaired/control CAS operations; arbitrary applications remain unqualified. [Contract and evidence](CAS_LAUNCHER.md).

The scoped CAS bootstrap now accepts an explicit hash-checked local client allowlist without recompilation when that list changes. Two builds of one test client pass GTX checks under different policies; arbitrary applications and libraries remain unqualified. [Evidence](STANDALONE_CAS_ALLOWLIST.md).

One scoped CAS bootstrap now handles four certified pipeline-factory styles in the same process, including reflection and a default descriptor. Two GTX comparisons and four no-dispatch controls pass; arbitrary clients and broader factory semantics remain unqualified. [Evidence](STANDALONE_CAS_UNIFIED.md).

The scoped standalone CAS bootstrap now also supports the certified argument-and-buffer-type reflection option pair. Two GTX repairs and native comparisons pass, with selected argument reflection fields matching across four hosts; complete reflection and transparent integration remain unqualified. [Evidence](STANDALONE_CAS_REFLECTION.md).

The scoped standalone CAS bootstrap now repairs its certified shaders through the public pipeline factory with zero options and null reflection. Two GTX comparisons and reflection/native regression controls pass; other options and transparent apps remain unqualified. [Evidence](STANDALONE_CAS_OPTIONS.md).

An experimental C++ reply gate rejects a locally simulated short success before the native video wrapper constructs a resource, in two guarded processes. No real short response, video allocation or installed-driver fix is established. [Evidence](VIDEO_REPLY_GATE.md).

A static video reply audit identifies a no-write NVIDIA private-tail function and a user-mode length-check gap on a hypothetical short successful reply. A CPU-only conservative bounds helper is tested; no real short reply, driver fix or video decode is established. [Evidence](VIDEO_REPLY_CONTRACT.md).

On a real video wrapper, a historically observed class-0/128 KiB request reaches a guard and is refused before IOKit; the native user-mode output capacity is 49 bytes on this profile. Kernel acceptance and video allocation remain unproved. [Evidence](VIDEO_BUFFER_REQUEST_GUARD.md).

An empty video context and a real Metal buffer coexist on the same shared object in two guarded processes; the buffer passes CPU checks before and after context release. This does not bind it to video or demonstrate GPU execution. [Evidence](VIDEO_CONTEXT_RESOURCE_COEXIST.md).

Two guarded processes create, associate and immediately release an empty video-context wrapper from Metal’s real shared object. No video resource or decode is established. [Evidence](METAL_VIDEO_CONTEXT.md).

Four Metal processes show the same real device/shared object relationship; retention and video use remain unqualified. [Evidence](METAL_SHARED_OBJECT.md).

A synthetic legacy-provider initialization probe uses the observed GTX device words and validates an ordered local selector guard. Actual video dispatch remains unqualified. [Evidence](VIDEO_SYNTHETIC_SEQUENCE.md).

Two own-process observations compare the real Metal-created GTX device configuration with object fields; meanings and video decoding remain unqualified. [Evidence](METAL_DEVICE_OBJECT.md).

Read-only current IOAccelerator analysis identifies a device type check and five configuration output words; no valid device values or hardware video are established. [Evidence](IOACCEL_DEVICE_CONFIG.md).

A synthetic video-provider probe reaches a locally refused `0x103` request after fabricated configuration. No real selector or video decoding is proved. [Evidence](VIDEO_SYNTHETIC_SELECTOR.md).

A guarded synthetic legacy-provider probe reaches a device-configuration dependency. One earlier attempt crashed before the added guard; hardware video remains unproved. [Evidence](VIDEO_SYNTHETIC_CONFIG.md).

The pinned 10.12.6 video-provider selector table differs from the current kernel dispatch evidence. This is static only and does not prove a live selector refusal. [Evidence](VIDEO_PROVIDER_DISPATCH.md).

A scoped re-audit recovers the historical legacy-video provider evidence and separately records current protected-file drift. No hardware video is demonstrated. [Evidence](VIDEO_LEGACY_BACKEND.md).

A pinned public-Metal test executable now receives the qualified native CAS repair through an explicit process-local bootstrap, without linking the project API. GPU and negative controls pass; arbitrary third-party and system-wide integration remain open. [Evidence](STANDALONE_CAS.md).

Four CAS SDK certificates were regenerated with the pinned decoder and tested on the current GTX profile. Two repaired runs and native defect controls pass their respective CPU oracles; the runtime remains an opt-in application adapter. [Evidence](CAS_SDK_REGENERATED.md).

The offline native CAS diagnosis now rejects incomplete/reordered disassembly and requires an exact listing reproduced by the pinned decoder. Two artificial false-acceptance cases are refused; archived cases retain their offline outcomes. This does not invalidate old policies or establish general compiler repair. [Evidence](CAS_DISASSEMBLY_COVERAGE.md).

The standalone opt-in bootstrap now serializes concurrent default-device initialization and reuses the same device for later calls. A pinned experimental client checks eight concurrent calls, one subsequent call, GPU output and refusal controls. Arbitrary applications and concurrent queue setup remain open. [Evidence](STANDALONE_ICB_MULTICALL.md).

The opted-in partial-grid adapter can chain two different certified compute pipelines from the same pinned registration, including partial and uniform slots. GTX producer/consumer controls test order, reuse and the 16-launch boundary. Broader shaders, native Apple ICB and transparent integration remain open. [Contract and evidence](PARTIAL_ICB_DUAL_PIPELINE.md).

Two isolated video-context witnesses correlate the owning process's registry entry with two mapped address ranges; both ranges cease to be covered after context close in these observations. This does not establish kernel-object destruction, fix the earlier explicit-unmap failure, or prove hardware video decoding. [Evidence and limits](VIDEO_OWNER_MAP.md).

The experimental partial-grid adapter accepts variable, bounded buffer sizes and aligned offsets for its two pinned shaders. A 21-process GTX cohort includes 21,652 invocations using the new layouts, fixed-envelope and uniform regressions, and negative controls; native constant-bank rounding can still reject some windows. [Contract and evidence](PARTIAL_ICB_VARIABLE_RESOURCES.md).

The offline native CAS recognizer now refuses candidates when the register changed by the repair is also referenced by another later instruction or by the output address. This is a conservative safety restriction, not a general proof of shader semantics. [Scope and validation](CAS_RECOGNIZER_SAFETY.md).

A second, exact buffer-transform shader executes through the bounded partial-grid adapter, with CPU-oracle and regression checks. [Evidence and limitations](PARTIAL_ICB_BUFFER_STENCIL.md).

An explicit opt-in project ICB path executes bounded partial 1D/2D/3D grids for the exact certified shader and resource profile. Arbitrary shaders and general Metal ICB support remain open. [Contract and qualification](PARTIAL_ICB_BOUNDED_PROFILE.md).

Scoped CPU compute ICB thread-grid dispatch accepts evenly divisible grids with bounded 1D, 2D and 3D GPU qualification; other profiles remain refused. [Evidence](UNIFORM_THREAD_ICB.md).

Qualified render-encoder creation can now be adapted automatically on one opted-in queue, with guarded fallback for unsupported passes. Bootstrap and pipeline registration remain explicit. [Evidence and limits](AUTOMATIC_RENDER_FACTORIES.md).

The scoped quad context combines indexed draw spans with vertex, pipeline and fragment transitions. [Evidence and limits](QUAD_RENDER.md).

Eight render states and sixteen flattened candidates pass bounded GTX execution and controls. [Evidence and limits](EIGHT_STATE_CATALOGUE.md).

A separate typed fragment context selects certified fragment argument buffers from the GPU and renders a native Metal texture in an adapted client. A later combined context is documented in [QUAD_RENDER.md](QUAD_RENDER.md). [Evidence and limits](FRAGMENT_BINDING_EXPERIMENT.md).

The scoped triple render context combines pipeline and vertex transitions with indexed draw spans. The adapted client checks native-image and CPU references, setter order and guarded refusal cases; transparent application support remains open. [Evidence and reproduction](TRIPLE_RENDER.md).

The typed render-pipeline context and argument encoder are now runtime-owned in the scoped adapter. GPU images, bounded lifetime/refusal checks and same-runtime rendering/compute regressions pass; transparent application integration remains open. [Evidence and reproduction](PIPELINE_RUNTIME_INTEGRATION.md).

An adapted laboratory client translates typed render-pipeline selection and changes a GTX image; 20 rendering and 16 compute hosts pass bounded CPU, native-image and negative controls. The client manually owns the context; runtime integration remains open. [Evidence and limits](TYPED_PIPELINE_RENDER.md).

A construction-only GTX/M1 comparison locates a missing typed render-pipeline encoder and compiler path. An offline transition planner is under development; no new GPU execution is claimed. [Observation, reproduction and limits](RENDER_PIPELINE_BOUNDARY.md).

The dual root combines certified vertex transitions and indexed draw spans for one adapted shader. [Evidence and limits](COMBINED_INDEX_VERTEX.md).

The typed vertex-buffer setter now resolves certified catalogue transitions on GPU using retained resource snapshots. The tested two-state, one-slot render path and negative controls are documented in [the scoped contract](VERTEX_BINDING_EXPERIMENT.md).

The typed render path now handles indexed device-pointer triangles in both element widths through an owned inline binding table. It preserves the v1 root prefix, retains index resources and checks exact pointer/format/span mapping before the existing sealed materializer. CPU/native image references and missing/foreign/wrong-kind/table/order controls qualify the path. [Exact evidence and limitations](INDEXED_RENDER.md).

Typed triangle draws and resets now preserve original AIR dataflow and feed the owned render-record/raster path. Independent producer, direct-draw and missing/order controls qualify dynamic geometry, preserved state identity, complete six-vertex rectangles and sealed-envelope refusals. This extends the earlier reset-only path without changing the core runtime. [Exact qualification, source and limits](TYPED_RENDER_DRAW.md).

The public render argument-root path now owns context construction/resource declarations and completion lifetimes. Twenty-seven final hosts pass 216 frames / 2,654,208 exact float channels, 168 reset dispatches and 66 expected API refusals; 216 ordinary native PSO programs match the pinned certificate. Sixteen fresh render/compute IRv2 regression hosts pass on the same new runtime. All 287 CPU tests pass and 87 system files stay unchanged. This remains scoped adapted-application support; native Apple ICB identity and transparent integration remain open. [Evidence and reproduction](RENDER_RECORD_ARGUMENTS.md).

The qualified typed AIR reset producer now clears a real render-state record before materialization and changes the resulting image correctly. Twenty-one final hosts check 168 frames / 2,064,384 exact float channels, 120 reset dispatches and 480 uint32 witnesses. Missing-dispatch and one-bit invalid-context controls retain the draw; direct/native-MSL references match. A C-linkage retained MRC factory serves the ARC host and restores its observer before scope activation. Fresh seven-object sources link an identical tested executable; the default path remains byte-identical. All 277 CPU tests pass and 87 system files remain unchanged. [Evidence and limits](AIR_RESET_RENDER.md).

Typed AIR reset lowering now preserves arithmetic/control flow and three additional ordinary buffer bindings. Ten final hosts pass 96 compute dispatches, 245,760 CPU-checked bytes, 1,548 uint32 outputs, 300 record resets and 144 translated/reference file pairs. Structural graph recognition reproduces the preceding qualified shader library byte-identically; execution remains pinned. All 266 CPU tests pass and 87 system files stay unchanged. No downstream render, factory integration, native Apple ICB ABI or speedup is claimed. [Evidence and reproduction](AIR_RESET_DATAFLOW.md).

An exact-profile AIR translation now executes one unchanged SDK-typed render-reset shader through NVIDIA's native compiler. Ten final signed hosts cover 84 compute dispatches, 138,240 CPU-matching bytes, 15,360 guard bytes and 45 translated/reference file pairs. Invalid contexts and missing dispatch preserve the expected records. This uses an explicit project context and does not implement Apple's ICB resource ABI. System and core runtime remain unchanged; no speedup or full Metal version is claimed. [Evidence and reproduction](AIR_RENDER_RESET.md).

Native code-buffer binding/readback observation now checks 56 matching private-buffer code copies, 46 unsubmitted QMDs and 28 repeat file pairs across 60 final hosts. All 48 raw-operation readbacks retain a PC-relative call to local program entry. CPU code and buffer identity stay unchanged; committed work is blit-only. Native ICB semantics and commit-time resolution remain unqualified. [Exact scope and evidence](NATIVE_COMMAND_BINDING_READBACK.md).

Native-command construction probes now separate typed ICB metadata refusal from raw diagnostic PSO acceptance. Six raw operations share a 64-byte native block with a local call target zero; witness cases retain that call, with vertex binding differing from the other five. Fourteen CPU staging copies remain identical after the original constructor. This is diagnostic evidence, not native ICB execution or a proven late-linker defect. [Scope and exact evidence](NATIVE_COMMAND_COMPILER_BOUNDARY.md).

The native MSL source render-command interface now covers reset, state assignment, direct/indexed draws and ordered command copying. Twelve new terminal processes check 1,093,632 exact float channels, 68,448 guard bytes and 33 native-reference image pairs, with raw-record equivalence on the unchanged runtime/materializer. This is an explicit project namespace and adapted source, not Apple native render-command ABI or reduced CPU state encoding. [Contract and exact evidence](NATIVE_RENDER_SOURCE_COMMANDS.md).

Certified render-state catalogues now permit GPU identity selection through native indirect-draw predicates. The 54-process reception includes 42 regressions and checks 1,093,632 new exact float channels, 68,448 guard bytes, 33 native-reference image pairs and 28 API refusals. Pipeline-only and resource-only controls pass independently; forced-candidate controls change 12,360/10,638 channels. All frames drain the pool and release software owners before commit. This uses CPU-expanded candidates, process-local project identities and adapted applications; native ICB/PSO identity, arbitrary GPU state packets, transparent integration and performance remain open. [Contract and exact evidence](GPU_RENDER_STATE_CATALOGUE.md).

GPU-generated scalar render records now control bounded counts/start positions through the scoped native draw route. The complete 42-host reception checks 638,976 new exact float channels, 1,622,016 including range regression, 68 native-reference image pairs and 1,362 identical raw pairs. Fifty-one invalid or missing occupied-slot records are suppressed on GPU. Four nonempty release probes observe scope/ICB destruction before commit; fragment textures/samplers remain alive and render correctly. Only the ICB runtime object changes. Pipeline/resource choice, native MSL render-command support, transparent integration and performance remain open. [Contract, source and evidence](GPU_RENDER_COMMAND_RECORDS.md).

The scoped render adapter now consumes a GPU-generated execution range through the public indirect-range selector, after an explicit native prepass. Ten new processes check 983,040 exact raster channels and 57,984 guard bytes; 48 complete images match native references. Twenty-two additional processes cover compute/adapter regression and construction-only metadata on the new complete archive. CPU-encoded draw contents, registered profiles and adapted clients remain required. [Contract, exact artifact and limits](GPU_RENDER_EXECUTION_RANGES.md).

Native-source GPU producers now select between two native argument-buffer banks and feed the existing compute materializer/resident transport. The final 28-host reception has 18 new GPU-command hosts and ten direct/CPU-ICB regressions: 16,224 new computed values, 8,112 sentinel controls, 45 verified GPU records and nine zero-CTA controls. All 159 CPU tests pass and 87 system hashes remain unchanged. The seven-object runtime is byte-identical; ordinary library/function construction and native getter restoration are qualified for the three-buffer producer root. [Source, auxiliary shader reconstruction, evidence and limits](GPU_ICB_TEXTURE_ARGUMENTS.md).

Existing CPU compute ICBs now execute the native texture/sampler/nested-buffer consumer correctly. Three fresh-process series plus one uncommitted metadata probe give 31 terminal hosts, 72 consumer dispatches, 32,448 computed uint32 results, 8,112 sentinel controls, 116,640 guard bytes and 180 direct/ICB identical raw-file pairs. All 144 CPU tests pass; 87 system hashes stay unchanged. The complete seven-object runtime is unchanged. GPU-generated texture commands have a separate qualification above; automatic indirect-resource lifetimes and nonzero CB2 offsets remain open. [Contract, preserved refusals and reproduction](ICB_TEXTURE_ARGUMENTS.md).

The native source backend now uses the existing ordinary library/function factory integration after one immutable library registration. Both pointer and reusable schemas preserve native PSO factories/reflection and automatic queue encoders, without manual function registration. Unlisted functions stay native; the older NAK registration is preserved. This remains scoped level 2 support. [Qualification and contract](NATIVE_SOURCE_LIBRARY_FACTORIES.md).

Reusable compute ICB contexts now preserve one owned Private buffer across completed generations. The 20-process cohort passes 6,411,264 exact consumer values, 464 premature prepare/reset refusals, 60 stale CPU-plan refusals, 80 retired-slot consumer refusals and three GPU-rejected prior roots. The complete reception has 52 signed terminal nonoverlapping hosts, including the preceding 32-process regression on the same seven-object archive. All 129 CPU tests pass. Only the ICB object changes; system files, OCLP and native command transport remain unchanged. This is level 2 opt-in support; native Apple resource IDs and transparent applications remain open. [Contract, evidence and reproduction](REUSABLE_ICB_CONTEXTS.md).

Stable pipeline identities in the project ABI now survive plan permutations and repeated native PSOs with different local sizes. GPU setters resolve the executable candidate; 32 final hosts pass, including 5,950,464 native consumer results, 72 complete context checks, six choices differing from the root representative, retired-scope controls and both legacy NAK references. The final archive changes only one of seven object files. Separate native-only reception and 122 CPU tests also pass. Apple resource IDs, stable ICB context identities and transparent applications remain open. [Details](STABLE_PIPELINE_IDENTITIES.md).

Source-lowered native producers now use public function argument encoders and the existing retained resource catalogue. A new seven-object archive passes 28 reception processes, including 5,492,736 exact native consumer results, both NAK references, 50 registration/factory/coexistence checks and encoder reuse. Six archive objects remain byte-identical; the ICB object gains explicit native-source function registration. Native pipeline factories and reflection stay native. Separate native-only controls and 117 CPU tests also pass. Stable ICB/pipeline identities, transparent applications and full hardware coverage remain open. [Contract, evidence and reproduction](NATIVE_SOURCE_FUNCTION_ARGUMENTS.md).

Native NVIDIA command producers now compile from supported public MSL calls through an opt-in header/type lowering, then feed the unchanged CommandIR v2 materializer and consumers. Sixteen native processes check 5,035,008 uint32 results / 1,258,752 active consumer invocations; record/error/guard probes and three NAK references complete a 22-host matrix. This implements a new source backend without NAK instruction import for the native producer. Original Apple ICB identities and transparent application integration remain open. [Exact implementation, pointer correction and limits](NATIVE_MSL_COMMANDS.md).

Native texture/sampler resource IDs are now GPU-qualified through direct argument writes, including a restricted mip view and sampler addressing controls: 90 dispatches, 48,672 checked uint32 words, 27,648 guard bytes and 18 native/direct identical raw pairs. No core runtime or system change is needed for this existing capability. The separate native ICB kernel fails specifically at `air.command_buffer` argument metadata; downstream command intrinsics remain unqualified. MSL 3.0/4.0 compilation of the old-operation test is not full feature support. [Evidence and reproduction](NATIVE_RESOURCE_IDENTITIES.md).

Generic compute/graphics imports now share the CAS constructor transport. A new complete archive passes 39 signed terminal nonoverlapping reception processes: 270,336 raster channels and 52,576 tessellation values match independent CPU oracles, with guards, native/empty controls and nested/cache refusals. This restores and consolidates the experimental graphics path; it adds no system-wide feature flag or general driver replacement. [Artifact and reproduction](SHARED_GENERIC_IMPORT.md).

The remaining combined FP64/ICB/native-render gates now share the exact-hash policy and PCI identity. A separate new seven-object archive passes 1,269 FP64/conversion dispatches / 6,095,853 checked results, the corrected ICB CAS path and native-defect controls, plus 11 render buffers / 135,168 channels. A baseline local-memory regression also passes on that artifact. This restores the bounded adapters on the current installed stack, not transparent application integration or a system-driver upgrade. [Fresh evidence and limitations](ADAPTER_PROFILES.md).

The initial changed-profile block is resolved for the tested compute/CAS path. The installed Metal driver's 262 differing bytes lie entirely in the CMS signature payload; code, data and CodeDirectory match the original. The runtime admits the two exact file hashes and resolves the current Metal device through its NVIDIA `10de:1198` PCI ancestry, replacing boot-specific IDs in the affected import/CAS/allocation gates. A new seven-object archive passes 190 compute dispatches, 570,616 exact uint32 results, 53,808 absent-without-dispatch controls and 106,650 correct CAS operations. All 87 system files remain unchanged during this work. This was the initial compute/CAS cohort, preceding the separate adapter qualification above; no global driver upgrade or speedup is claimed. [Profile evidence](DRIVER_PROFILES.md) · [Accounting and qualification](MEMORY_ACCOUNTING.md).

The exact qualified 8/16 KiB private-frame profile change is integrated into the common MRC import implementation. A new seven-object public source rebuild has its own GTX qualification: 226 compute dispatches, 612,120 exact output uint32 values, 111,872 guard bytes and 77,376 expected computation words absent in no-dispatch controls. A one-instruction differential yields 704 changed witnesses with 2,112 other arithmetic words identical; CAS coexistence preserves 106,650 correct operations. Constructor/refusal controls and legacy local/spill profiles pass. This is a bounded opt-in import extension, with no installed-driver change, hardware-video success or performance claim. [Commands, exact archive and limits](LARGE_LOCAL_MEMORY.md).

The optional resident-batch SDK snapshots records, source-slot barriers and resource footprints. Its bounded laboratory cohort passes 292 dispatches across 108 main trials: ten four-entry batches have all six pairwise intervals interleaved; 28 split batches preserve their midpoint boundary. Thirteen actual refusal cases run in each successful process; source slots are reset before user execution. The module owns its carrier encoder; ordinary Metal concurrency and general memory visibility remain unqualified. [Contract and independent public-artifact results](NATIVE_RESIDENT_BATCH.md).

The human administrator helper now opens and closes the normal NVDA user client successfully under UID 0, with a terminal inherited lease and no external method calls. The native video packet/decoder contract remains unresolved and zero hardware images are proved. [Exact scope and audit](VIDEO_ADMIN_ACCESS.md).

Native resident overlap: 34/34 bounded candidate pairs interleave in three laboratory processes, with 110 correct user dispatches including serial controls. A separate seven-object build from public sources passes its own 20-trial serial qualification and 16/16 candidate pairs: 62 correct dispatches, 20,992 raw sync/output words and 83,968 parameter bytes checked. Four independent state allocations and before/after GPU readbacks support the isolated intermediate-wait change. Native shader code, the installed stack and common runtime sources remain unchanged; the ordinary encoder still reports serial. This is a level-1 prototype, with no simultaneous-instruction or performance claim. [Source, exact scope and reproduction](NATIVE_RESIDENT_OVERLAP.md).

Native start follow-up:17terminal/nonoverlapping hosts,18exact software images/2,073,600NV12bytes and1952mock ABI checks. Five current-board cases observe the real native start; four retain its context-policy caller stack; three final V8 cases create the first CV pixel buffer at0/non-null. All11hardware creates remain refused, with zero images. The three software cases preserve12FinF/Inva-12782 replies. The next candidate session enumeration/failing branch is not yet observed. No native method/table replaced, unknown private function directly called, system change, new Metal feature or benchmark. [Evidence and source](VIDEO_NATIVE_START.md).

The native factory loader returns0/non-null; the real AppleGVA10.0.20 accelerator interface is resolved at4577. Seven same-executable hardware cases isolate its System Support policy: three current-board copies change Strt/public create to-12913, while two original/two wrong-board controls retain-12906. All hardware cases have zero images. The19terminal/nonoverlapping hosts include30exact software images/3,456,000NV12bytes,608public-resolver and512GetFactory mock controls, one preserved failed link and20explicitly retained FinF/Inva replies at-12782. The next native start-method failure and full service lifetime remain open. A corrected cache-import parser has six passing portable tests. Protected files, both policies, OCLP and common runtime remain unchanged. [Evidence and reproduction](VIDEO_FACTORY_POLICY.md).

The preceding local native video transport milestone passes bounded software decoding:24owned-transport images are exact; its33host cohort contains48images/5,529,600CPU-matching NV12bytes and four preserved qualification failures. Its final7host artifact completes all observations; hardware-required creation remains-12906/zeroimages. It observes AppleGVA10.0.20 after two GVA candidate selections. The factory return was still open at that milestone; the investigation above establishes it. [Evidence and limits](VIDEO_LOCAL_SERVICE.md).

New peer milestone: 13 signed terminal hosts, 18 software images / 2,073,600 exact
NV12 bytes, 14 consistent peer observations across 7 distinct births, and two
independent bounded service-log windows. All nine hardware creates still fail
-12906. REA 6.4.0 / Ghidra 12.1.4 and bounded cache analysis map the native service entry
through its callback to a `Strt` block that can propagate the old selector's
error; the failing runtime branch and complete root cause remain unproved.
Six same-binary cases toggle only peer observation, preserving replies. System,
policy, OCLP and common runtime/archive remain unchanged. No new hardware codec,
Metal feature, M1 run or benchmark. [Evidence and reproduction](VIDEO_PEER_IDENTITY.md).

New routing milestone: 19 signed terminal nonoverlapping host runs, 24 software
images / 2,764,800 exact NV12 bytes, 1,824 mock forwarding calls and 210 bounded
summary controls. Three present-key cases reach the decoder service: `uber=0`,
then `Strt=-12906`; six native/wrong-key controls have no such observed
exchanges. All 13 hardware creates fail before images. Static matching bundle
metadata is pinned; live peer identity, remote providers/registry and complete
root cause remain unverified. System, policy, OCLP and common runtime sources
are unchanged. No new Metal function, M1 run or benchmark.
[Evidence, scope and reproduction](VIDEO_ROUTING.md).

New dependency milestone: 19 terminal nonoverlapping processes, 24 software images / 2,764,800 exact NV12 bytes, 38 public query controls and 110 CPU scope checks. Twenty-two real queries target nvAccelerator registry ID 4294968458. Three scoped `IOGVACodec` presence substitutions change GVA selection (178 entry observations versus 87 in native/wrong-key controls), but all 13 hardware creates still fail at -12906 with zero images. This establishes a selection barrier; a complete decoder fix and hardware execution remain unproved. [Evidence and reproduction](VIDEO_DEPENDENCIES.md).

Static video-method analysis now identifies the eight-entry legacy IOAccelerator method table and its SDK kernel layout; submit/get-buffer entries declare 136/8-byte inputs and variable outputs. No video selector was explicitly invoked in these witnesses, and the resource/command ABI remains unqualified. [Method contract](VIDEO_METHOD_CONTRACT.md). Static ownership analysis identifies same-task and same-accelerator checks before context association and a stateful start. A pinned static stop chain reaches the inherited cleanup through the NVIDIA and video parent overrides; live post-association cleanup and video execution remain unverified. [Resource ownership](VIDEO_RESOURCE_OWNERSHIP.md). Two isolated type-6 shared-client opens were refused with `kIOReturnUnsupported`; the originating branch remains unproved. [Shared client](VIDEO_SHARED_CLIENT.md). With an ordinary same-GPU Metal device retained in the calling process, the same type-6 open and close succeeds twice; a Metal queue also succeeds twice. Association and video execution remain unproved. [Same-process comparison](VIDEO_SHARED_METAL.md). Two same-process association requests subsequently returned success and both pairs closed normally; no video selector or decode is qualified. [Association witness](VIDEO_CONTEXT_ASSOCIATION.md). Static user-mode analysis now connects the native wrapper constructors and context buffer request; valid inputs, lifetimes and video execution remain unqualified. [Buffer path](VIDEO_BUFFER_USER_CONTRACT.md). Static CF lifecycle analysis finds a conditional shared-client selector during resource release; it has not been invoked or qualified. [Buffer lifetime](VIDEO_BUFFER_LIFETIME.md). Static analysis links shared selector 1 to NVIDIA lookup/pending-release handling and the inherited resource-deletion path; no selector was executed. [Shared deletion](VIDEO_SHARED_DELETE.md).

On the current exact profile, a fresh four-process cohort requalifies user-mode `nvAccelerator` type-3 open/close: inventory, wrong-target rejection and two successful opens/closes. No external method, GPU video command or hardware decode is established. [Evidence and reproduction](VIDEO_CONTEXT_CURRENT.md).

A later donor comparison covers the entire 1,026,192-byte pre-signature region of the current GeForce file against a pinned upstream donor; only two validated signature-layout size bytes differ. The missing historical file is not inferred from that comparison, and video/RM qualification remains open. [Details](VIDEO_DONOR_COMPARISON.md).

Video-profile recheck: five of 83 historical file hashes changed. All 28 archived GeForce video-table words and their relocation metadata, plus 11 archived function ranges (1,217 bytes), match the current file. This partial static comparison does not qualify the current video path or the prepared privileged RM test. [Profile drift and reproduction](VIDEO_PROFILE_DRIFT.md).

The full goal remains **incomplete**. This is a development source snapshot with private ABI dependencies, not a production display-driver release. No percentage of total completion is assigned: the remaining hardware/API scope is not bounded enough to make that number meaningful.

Public codec follow-up: fourteen new terminal processes produce18exact software images/2,073,600activeNV12bytes across H.264 and MPEG-2 controls. Nine hardware-required creates still return-12906/zeroimages with original and alternative model tables. The native policy site is not observed on our thread, despite working synthetic calibration. A new MPEG-2 CPU fixture is independently generated/decoded by pinned FFmpeg on arm64. The model eligibility result therefore does not repair these public paths. Offline VT error-site mapping identifies a next observation target, not the runtime cause. [Results and reproduction](VIDEO_CODEC_SELECTION.md).

New video eligibility result: AppleVA5.1.1 and VideoToolbox3330.13.105 are actually loaded; AppleGVA is absent from these recorded processes. A pinned zero-argument availability query returns0 in three fresh processes receiving a minimal `iMac11,1` policy entry, while four native and three wrong-model controls return-8973. Returned data changes only inside the test process; resident instructions and system policy stay unchanged. Seventeen new native processes,256 synthetic ABI cases and six CPU-matching images are audited separately from the earlier transport milestone. No hardware video or global H.264 cause is established. [Evidence and reproduction](VIDEO_ELIGIBILITY.md).

Video transport: the original NVIDIA WebVA matches its support copy and provides two constant-return factory stubs. An independent CPU decoder validates six iMac software images / 691,200 active NV12 bytes exactly. Hardware-required VT still fails `-12906`, plain and observed, with zero images; bounded traces show Metal initialization without proven video submission. Thirteen probe processes are terminal, 768 synthetic ABI cases pass, and 83 system files / 36 runtime sources / OCLP remain unchanged. The first missing-reference control stays incomplete. No hardware video, benchmark or new Metal feature is claimed. [Investigation and reproduction](VIDEO_TRANSPORT.md).

A separate pinned public-Metal client qualifies default compute-descriptor CAS pipeline creation in a process-local experiment. [Evidence and boundaries](DESCRIPTOR_CAS.md).

| Area | Evidence from local work | Remaining limitation |
| --- | --- | --- |
| AIR → NIR → NAK SM30 | Compiled programs executed on the reference GTX with CPU output comparisons | Does not implement a Metal runtime or replace the installed compiler |
| Shared memory / atomics | Earlier bounded cohorts covered 48 KiB/group and 1,024 threads/group | Scope is the tested programs and synchronization patterns |
| Native weak-CAS result | Causal repair with original/replay/NOP controls; later semantic recognition | Targeted, process-local repair; not every Invalid Resource issue or all CAS programs are solved |
| Native heaps, aliases, fences, events | Working scenarios using existing native APIs | Existing capabilities, not functions newly added by KeplerMetal |
| CPU/generated command paths | Scoped native-command adaptation with CPU oracles, guards and negative controls | Custom IR ABI; Apple ICB identity and `gpuResourceID` remain unsupported |
| Device argument encoders | Fully selected milestone: 192 cases, 8,239,104 uint32 values, 2,059,776 invocations, 127,576,064 guard bytes; 12 M1 reference trials / 156 common semantic files matched | Counts include selected controls/lifetime cases, not full Metal conformance; no general speed claim |
| Three-pointer argument layout | 60 selected typed trials plus 3 legacy trials passed on the preceding library | Requires qualification on the later function-encoder candidate |
| Function argument encoders | Real native metadata preserved; library `ee9c71cb…`: 64 dataflow trials, 60 three-pointer trials and 4 encoder-reuse trials PASS; 12 same-source M1 trials / 156 common files matched | Bounded layout/producer contract; not a general Metal implementation |
| Native resource ABI | Producers load root pointer and launch dimensions from native CB1; 64 trials PASS after correcting an initial experimental CB0 mapping failure | Producer qualification uses one 32-thread group; other producer geometries remain unqualified |
| Previous registered pipeline factory contracts | Library `c8571cf1…`: six public factory variants, 128 GTX trials, 12,358,656 exact uint32 results, 3,089,664 counted consumer invocations and 165,449,536 guard bytes; 17 supported CPU variants, 24 expected rejections, one pending asynchronous scope-release case; 12 same-source M1 trials / 156 common files matched | Six functions need explicit registration/pins. Reflection is an adapter backed by native argument metadata. Descriptor max threads uses automatic/default 0; the native constructor returned 1,024 for a request of 32, so smaller limits are refused. No arbitrary-library compilation or transparent application integration |
| CAS transport regression | After a same-thread descriptor import, 106,650 CAS operations / 90 submissions passed; eight import/pin rejections remained effective | Bounded native CAS repairs and transport-state cleanup, not a general installed compiler repair |
| Managed dirty-buffer abandonment | Native-only diagnostics reproduced retained objects in bounded cases | Earlier cancellation FAIL retained; no general permanent-leak claim or workaround |
| Video / display / power / full VRAM management | Inventory and focused investigations | No full modernization or complete hardware coverage demonstrated |
| Linux/FreeBSD driver comparison | Reference archives studied and differences classified | No proprietary correction has been ported into the installed macOS driver |

The final library also passed 9 targeted three-pointer regression cases. A separate complete rebuild of all seven runtime objects from the public source (`f110430d…`) passed 4 GTX smoke trials with 457,728 exact uint32 values, 114,432 counted consumer invocations and 5,052,992 guard bytes. Its full 64-case suite was NOT RUN; it does not inherit the other artifact's qualification.

A 4 MiB public Metal buffer now has a bounded observed link to the same IOAccelerator shared wrapper created for the GTX in two processes. The resource field is located through pinned runtime metadata and getter code without calling that getter. This does not qualify a video buffer or prove GPU execution. [Evidence and reproduction](VIDEO_RESOURCE_IDENTITY.md).

## Evidence boundaries

Milestone library hashes:

- Last published device-argument qualification: `edd584b05b94ca536ab65a1976440a52e521a15657e0b02f843be1a422d7b176`.
- Function smoke candidate: `77cbf183798f9883e3ebf6c61f49c076a3ad20d39a451a5e312bfa323c31bf31`.
- Subsequent function candidate: `ee9c71cb26cb4d109be8875424e0f0be487c8f91a671f26ce0068348172ec5af`.
- Previous registered synchronous pipeline candidate: `b19f78099eb6bb9b644e481902cbcbed829760f8e5ff61114d2bbb5fbaf66dd7`.

- Current six-factory candidate: `c8571cf130546db4bc224573b0bb684c3cd537df95df7262be266b36a200869e`.

These are historical build identities, not downloadable artifacts. The original source tree had no Git commit. `SOURCE_SNAPSHOT.json` records the exported source hashes and publication edits. Private binary result archives are intentionally excluded; the published tools allow inspection of the checks, but a summary is not independent proof of hardware execution. A new full source build has a different artifact identity and does not inherit old GPU qualification.

The milestones below supersede the initial descriptor-limit and library-integration gaps for their explicitly registered subset. Current remaining work includes arbitrary shader/library support, broader resource ABI and hardware qualification, and transparent application integration. The six factories are integrated for the explicitly registered subset; transparent support for arbitrary application libraries remains open. Preserve validated native behavior rather than reimplementing it unnecessarily. [Detailed contract](NATIVE_FUNCTION_PIPELINES.md) and [current validation summary](pipeline-contract-validation.json).

No new driver performance benchmark is claimed. Earlier application batching improvements mixed submission and wait effects; NAK was slower than the native path on two tested workloads. API extension, correctness repair, and application optimization are distinct results.

The current public-source seven-object rebuild (`0351b1bd26971e3f7c9e8b77d89a9babd8a9c1fb19cec3cadc38b30bf26f7f2c`) passed the full archive link and CPU link check, then four asynchronous-descriptor GTX smoke trials: 457,728 exact uint32 values, 114,432 counted consumer invocations and 5,052,992 guard bytes. The 128-trial suite was NOT RUN on this separately rebuilt artifact.

## Native thread-limit repair

Library `9e9a2b79085d5b031148e7a5294d1383325def18220b614b12cb94170487f036` passed 172 GTX trials: 17,393,664 exact uint32 results, 4,348,416 counted consumer invocations and 221,032,448 guard bytes. This comprises 128 factory/dataflow cases with a requested limit of 32 on descriptor variants, and 44 additional cases including producer groups 64,128,256,512,1024 plus an automatic-limit control. Seventy CPU contract cases and 42 pending-scope/lifetime cases passed; 12 native M1 trials / 156 common semantic files matched.

The earlier smaller-limit refusal is superseded only for this explicitly registered subset. The repair initializes the existing native PSO field, preserving its original getter/class and shader optimizer, and rejects invalid local sizes on explicitly adapted encoders. Unadapted encoders, arbitrary-library shader attributes, global compiler/runtime support and general driver modernization remain open. The producer only generates commands at grid index0; these cohorts do not provide an independent invocation witness for every lane. No speed benchmark was run. [Details](NATIVE_FUNCTION_PIPELINES.md) · [Current evidence](thread-limit-validation.json).

The separately rebuilt public seven-object archive `00736648654c2eba1b7511d0bcdace653aa864004c2f58b4b7efb168844b0470` passed the full archive link and CPU link check, then four GTX asynchronous-descriptor smoke trials with the corrected 32-thread limit: 457,728 exact uint32 values, 114,432 counted consumer invocations and 5,052,992 guard bytes. Its full 172-trial suite was NOT RUN.

## Ordinary command creation on the scope-owned queue

Library `7ae40bfa1148cf1ef8eff0e5f769b30f554da1753beb61745942d8ebad295d1d` passed 236 GTX trials in 59 cohorts: 24,717,312 exact uint32 values, 6,179,328 counted consumer invocations and 307,511,008 guard bytes. This combines the 128-trial six-pipeline matrix and 108 additional trials for the other retained queue/compute factory combinations. The tested reception client contains no manual `adaptComputeEncoder:` calls. Twelve same-source native M1 trials have 156 common semantic files matching.

Twenty native-only observations established the queue/encoder factory baseline. Ninety-three contract cases cover automatic adaptation, retention flags, isolation of another queue, repeated encoders and four-thread factory creation. Another 168 lifecycle/factory cases include restoration with live objects, saved wrapper IMPs after restore, pending asynchronous requests, and a native one-buffer pool wait. The pool control submits one empty command buffer, no user kernel, and verifies its completion; its restoration duration is diagnostic, not a performance benchmark.

Other queues and preexisting command buffers stay native. IR dataflow still requires retained command buffers; unretained factory GPU IR dataflow was NOT RUN. Explicit registration/pins, general library/compiler support, full hardware modernization and transparent unmodified-application integration remain open. No new performance gain is claimed. [Current evidence](ordinary-queue-validation.json).

The separate seven-object public rebuild `7e19905f330d501f3c01299232d878c09b9f5ac3a02bed4b078148e8eb50ef7e` passed the full archive link and CPU link check, then four GTX smoke trials via retained-descriptor command buffers and concurrent-descriptor compute encoders: 457,728 exact uint32 values, 114,432 counted consumer invocations and 5,052,992 guard bytes. Its full 236-trial suite was NOT RUN; it does not inherit the lab archive's qualification.

## Ordinary native library and function factories

Library `1656923d0fd416fc25d75f0024736fc368f7c0e4285911c90625a71078efd727` passed 296 GTX trials in 74 cohorts: 31,583,232 exact uint32 results, 7,895,808 counted consumer invocations and 386,434,048 guard bytes. The 128-trial pipeline matrix uses the default data/plain-function route. Another 168 trials cover the remaining library/factory combinations with basic, barrier and copy semantics. Twenty native-only factory observations, 82 library contract cases, 98 lifecycle/contract cases and 93 legacy contract cases passed. Those case counts include common contracts repeated across lifecycle cohorts; they are not a count of distinct Metal features. Twelve native M1 trials using the exact client/helper source have 156 common semantic files matching.

One explicit registration snapshots the source, carrier and six programs, validates all pins and prepares six native PSOs. Ordinary data/URL/file library creation and five function selectors then attach registered profiles to real native functions. Aliases preserve the native name, and function lookup imports no additional program. The tested client makes zero manual function registrations and zero manual encoder adaptation calls. Unregistered consumer libraries remain native. Five invalid registrations caused zero native imports; duplicate registration was refused, and mutating all caller inputs afterward did not alter the stored profiles. Restoring/releasing the scope restored live library/function objects and preserved pending asynchronous pipeline completion.

The initial GPU preflight failure was a faulty control ordering: it expected the matching producer library to fail after automatic activation. The native unsupported-AIR control now runs before registration. The runtime archive was unchanged by this test correction; failed runs remain preserved. This resolves that preflight, not an arbitrary native compiler defect.

The separately rebuilt public seven-object archive `c907868266c2d86a0d53f2072e9e496f7e0ebea3690598c8231180e81e46a260` passed the full archive link/CPU check and four GTX file/alias/asynchronous-descriptor smoke trials: 457,728 exact uint32 values, 114,432 counted consumer invocations and 5,052,992 guard bytes. Its full 296-trial suite was NOT RUN.

The 83 tracked system files and OCLP remained unchanged. No new performance benchmark was run. This is level 2 integration for six pinned functions, not arbitrary-library compilation, full Metal 3/4 conformance or a modernized installed driver. Local/scratch memory and register spilling, memory pressure/full VRAM coverage, video engines, display and power integration remain among the broader hardware work. [API details](NATIVE_FUNCTION_PIPELINES.md) · [Current evidence](library-function-validation.json).

## Local/scratch memory and register spilling

Library `59f3a04d6c9929ec5c22034234e27006675174e076855df26a5b584f88f245ac` passed 180 positive trials and 48 no-dispatch controls in 19 cohorts. Native and NAK kernels cover private arrays of 128, 1,024 and 4,096 bytes/thread, plus named scalar values held across a barrier to induce real compiler spills. Group sizes 1,31,32,33,64,128,256,512,1024 and selected multigroup launches passed. The CPU oracle checked 269,040 output uint32 values, 67,260 per-invocation witnesses and 116,736 guard bytes. Input buffers were also compared in full. The output checksums exercise the private arrays; this is not a byte-for-byte readback of every internal scratch location.

Seven native compiler-container observations found 128–4,096-byte explicit private frames and 24/224-byte native compiler spills. NAK64/96 generated 28/156 scratch bytes with 7/39 spill and fill instructions; forced spilling at 18 actual GPRs generated 80 bytes and 20 spills/fills. Imported allocation uses a compatible native frame, including a 224-byte pressure carrier where required. Fourteen CPU contract cases passed. On the same thread, a local import followed by descriptor import preserved 106,650 correct CAS operations and eight rejection controls. Eight ordinary-library regression trials passed with 915,456 exact uint32 values.

The initial guarded control imported with native control word11=0 produced unchanged output and failed the oracle. The same program passes with the previously qualified word11=576 reserve. A decoder guard initially stopped this before GPU execution because that reserve adds 1,024 to the allocation word for the pinned profiles. Failed runs and CPU-only refusals remain preserved. The native local-allocation fields stay unchanged; instruction count/GPR and the explicit control reserve are the only metadata changes.

This is a bounded, explicit compiler/backend transport extension. The native Metal implementation already supported local memory. Larger frames, external CRS, arbitrary shader/library/resource layouts, sustained pressure and transparent application integration remain open. No M1 reference or new performance benchmark was run for this cohort; the earlier M1 library/function results have a separate scope. [Details](LOCAL_MEMORY.md) · [Evidence](local-memory-validation.json).

The public seven-object rebuild `10dd7a21f8755ff16af83e8c09bec746c9d93da89e37e95d24c8466197f05481` passed archive/link/CPU checks and 24 artifact-specific imported GPU trials (4 KiB local arrays and forced spilling). Its full 180-positive/48-negative matrix was NOT RUN. A separate native-only build regenerated the Metal library and host from public text and passed three local1024 trials. The regenerated-native workflow needs no archived binary fixture. All these executions used the existing common laboratory reservation root.

## MSL/AIR local-memory frontend

The same original MSL now compiles through AIR → NIR → SM30 for the local-array and register-pressure programs. The new cohort passed 180 compute trials and 48 missing-dispatch controls, with 269,040 exact uint32 outputs and 168 native/AIR input-output files matching. Eight offline contract cases passed. Runtime `59f3a04d…` is unchanged. This covers three buffers, a static 16-byte constant block, full 1D groups and the pinned local allocation; arbitrary shader/resource layouts, external CRS and transparent integration remain open. No new benchmark or M1 reference. [Details](AIR_LOCAL_MEMORY.md) · [Evidence](air-local-memory-validation.json).

## Deep control flow — partial qualification

Native source depths through64pass84trials; depth96FAILS12trials. An instrumented96variant writes entry witnesses for all4,484invocations but no final result. Cause unresolved; no hardware limit inferred. Separate allocation-preserving AIR/NAK imports with compiler CRS requirements1024/1536/2048bytes pass60trials;48no-dispatch controls pass.215,232exactuint32results and120native/AIR files match. Runtime63840c89adds decoded allocation evidence only; control→descriptor→CAS regression passes106,650operations and8rejections. NAK depth40using the failing96carrier is NOT RUN. The standard matrix staysFAIL. [Details](CONTROL_FLOW.md) · [Evidence](control-flow-validation.json).

## Native allocation correction — two profiles

The unchanged NVIDIA code for source depths65/96 passes24 trials after increasing only native metadata words9/11 to a4,096 reserve. The independent CPU oracle checks35,872 exact uint32 values and8,968 invocation witnesses. Original-payload replay and simple512-byte rounding remain numerically defective in48 comparison trials. Code hashes match across the variants; decoded native allocation changes are checked. This is an opt-in process-local experiment, separate from the shared runtime and installed driver. Code identity concerns constructor payloads, not an independent resident-instruction capture. Additional profiles, rejection/concurrency qualification and a general allocation rule remain open.

Two native M1 references pass72 positive and24 no-dispatch trials in total; one loads the exact original iMac metallib without frontend recompilation. Some M1 groups explicitly shrink to1 because the native pipeline maximum is384. These are semantic references, not SM30 or performance validation. Separate GTX controls pass with a104,000-byte native program and4,656-byte spill frames; sampled unmodified nested65..72/80/88/96 remain defective. The83 tracked system files and OCLP are unchanged. No new benchmark. [Details](NATIVE_CONTROL_RESERVE.md) · [Evidence](native-control-reserve-validation.json).

## Native allocation qualification — 17 profiles

The strengthened standalone constructor experiment passes228 GPU trials on17 distinct native profiles, with340,784 exact uint32 values,85,196 invocation witnesses and153,600 checked guard bytes. This includes24 lifetime trials after overwriting caller inputs and draining the factory pool. Complete payload and code identity are checked after the original constructor. The48 replay/rounding comparisons remain numerically defective;24 missing-dispatch controls and10 actual pre-dispatch API refusals match their required outcomes. A104,000-byte native program and a4,656-byte spill frame pass with the tested allocation. Eleven semantic comparisons check264 matching files, partly against the archived M1 reference; no new M1 execution or benchmark was run.

At that standalone milestone, the83 system files, OCLP and shared runtime archive remained unchanged. It was explicit level1 integration. Its common-runtime work is superseded by the API milestone below; the historical evidence remains scoped to its original archive. [Standalone details](NATIVE_CONTROL_RESERVE_QUALIFICATION.md) · [Evidence](native-control-reserve-qualification.json).

## Native allocation in the common MRC runtime

`KPCreateCertifiedNativeAllocationPipeline` now snapshots a pinned library and certificate, preserves native code, increases only allocation words9/11, and shares the CAS/local/descriptor mutex with a thread-local scope. The six-object lab archive `5636b0d0…` passes228native trials on17profiles,24missing-dispatch controls,16API refusals, controlled simultaneous factory creation,106,749correct CAS operations, and36local/spill regression trials. Total383user command buffers comprise359compute dispatches plus24missing-dispatch controls, with822,116exact uint32 results and161,152guard bytes. All83system hashes and OCLP are unchanged. No benchmark or new M1 run was performed.

A real adapter race was found and fixed: CAS restoration was checked against an IMP sampled before the common lock. The fixed core records restoration while still holding that lock. The failed pre-fix process and an unavailable-profile harness exception remain preserved; neither involved a faulty GPU result. The concurrency test runs GPU computations serially after the factory overlap. The descriptor prelude checks pipeline construction; its producer is not dispatched here. The full historical296-trial suite is NOT RUN on this archive. This is level2 integration for adapted applications, not a driver installation, a general allocation rule or complete Metal3/4 support. [Contract](NATIVE_ALLOCATION_API.md) · [Evidence](native-allocation-runtime-validation.json).

## Allocation thresholds and new104/120programs

The common API/archive is unchanged. Two newly compiled native programs,104/120source nesting, now pass24lifetime trials on each common/public archive. Four sampled adjacent512-byte settings distinguish unchanged-output failures from correct results:65→2560,96→3072,104→3584,120→4096; the preceding aligned setting fails in each case. New experiments total120correct trials and48numerical failures preserved,179,360exact uint32 values and86,016guard bytes. The25historical plus two new listings are checked against every encoded word. Their lexical metrics do not establish dynamic hardware CRS depth. A universal allocator, measured VRAM savings and performance remain open; the subsequent bounded QMD mapping is described below. No new system, OCLP or M1 changes. [Details](NATIVE_ALLOCATION_THRESHOLDS.md) · [Evidence](native-allocation-threshold-validation.json).

## Native QMD allocation fields

Read-only own-process capture validates12uncommitted and15captured-then-committed QMDv00_06records on source104/120profiles. LOW/HIGH match the aligned native frame; CRS is align512(metadata word11)+512. The prepared decoded budget is(LOW+HIGH)*32+CRS. A metadata reserve4096 produces CRS4608 versus3072native, preserving LOW/HIGH/GPR and NVIDIA constructor-payload code identity. Nine corrected compute trials return3564exact uint32values and891witnesses; six native trials retain2376incorrect A5words. All7680guard bytes and7680parameter bytes are intact.45user command buffers comprise15compute and30initialization/readback blits. The separate public archive passes three of the corrected trials. Fourteen malformed-stream controls are refused entirely offline. An earlier three-QMD preflight and one CPU-only compile failure remain preserved and excluded from primary counts.

Runtime/system/OCLP are unchanged. Captures precede ordinary commit: resident-QMD readback and independent exclusion of commit-time rewriting were NOT RUN. Native unchanged output does not identify where execution failed. General allocation requirements, dynamic stack depth, physical VRAM usage, transparent application integration and full hardware coverage remain open. No new M1 run or benchmark. [Details and reproduction](NATIVE_ALLOCATION_QMD.md) · [Evidence](native-allocation-qmd-validation.json).

## Segmented native control — shape matters

Two consecutive nested blocks48+48pass three native trials. Blocks65+55fail three native trials and three standalone2,048trials, then pass three standalone2,560trials and three common-API4,096trials. New totals:15compute submissions plus30DMA command buffers,9correct trials/3,564exact uint32values/891witnesses,6retained failures/2,376incorrect A5words,7,680guard bytes and7,680parameter bytes intact. The runtime/archive is unchanged. Prepared CRS for65+55is2,560at native/2,048,3,072at requested2,560and4,608through the common API. Its244`joinat`instructions exceed the previous fully nested120program's242, although it passes at2,560whereas the full program failed at3,584. Old controls are re-audited without GPU replay. No exact minimum or general allocator is established.

Recursive/event-stack oracles pass1,234comparisons, including existing nested/serial references. The abstract single-control-path model is not a hardware certificate. Frame/code differences between programs remain explicit; only constructor allocation words change within each comparison. No new segmented qualification is attributed to the separate public archive. System/OCLP stay unchanged; no M1 run, benchmark or measured VRAM saving. [Details](NATIVE_SEGMENTED_CONTROL.md) · [Evidence](native-segmented-control-validation.json).

## Native control reservation proposals

The CPU-only analyzer binds 29 SM30 listings to code bytes and explores a restricted SSY/JOIN path abstraction. Its 18 synthetic tests include strict refusals and two native layout counterexamples. It never certifies a hardware SIMT bound or applies an allocation automatically. Two exact source96 variants pass 24 new GTX compute trials at manually selected reservations of 3,584/3,072: 35,872 exact uint32 results, 8,968 final invocation witnesses and 12,288 intact guard bytes. Forty-eight input/output files match their archived 4,096-byte counterparts. Native failures and original nested96 at 3,584 are re-audited without GPU replay; historical counts stay separate.

The standalone experiment, common runtime/archive, 36 runtime sources, 83 system files and OCLP remain unchanged. New GPU trials are not attributed to the separately rebuilt public archive. No new Metal API, M1 execution, benchmark, measured VRAM saving or transparent application support. The general allocator and full hardware objective remain open. [Contract and reproduction](NATIVE_CONTROL_PROPOSALS.md) · [Scoped evidence](native-control-proposal-validation.json).
