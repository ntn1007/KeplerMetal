# KeplerMetal

Open source research for modernizing the NVIDIA Kepler graphics stack on macOS.

Latest native investigation: an explicit allocation API now shares the MRC import runtime, mutex and thread-local context. It preserves NVIDIA-generated code and passes228 GPU trials on17 native profiles, plus refusal, lifetime, CAS, local-memory and controlled factory-concurrency checks. A concurrency race in our CAS adapter is corrected. No installed-driver change or speedup is claimed. [Contract and limits](docs/NATIVE_ALLOCATION_API.md).

[Français](README.fr.md) · [Build from source](docs/BUILDING.md) · [Dependencies](docs/DEPENDENCIES.md) · [Status](docs/STATUS.md) · [Architecture](docs/ARCHITECTURE.md)

The reference device is a GeForce GTX 880M, GK104 / SM30, with 8 GiB VRAM in an Intel iMac. The project studies two independent areas:

1. **NVIDIA stack modernization:** diagnose and correct specific native shader/runtime behavior, compare driver generations, and measure any improvement.
2. **Metal extensions:** implement selected missing resource and command functionality using the working native driver and scoped, application-side adapters.

This is an experimental source release. It is **not an installable replacement display driver**, a claim of Metal 3/4 conformance, or a Linux-to-XNU driver port. The integration currently requires an explicitly adapted application. Existing macOS/OCLP components stay in place.

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
