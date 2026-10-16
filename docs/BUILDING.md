# Build from source

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
