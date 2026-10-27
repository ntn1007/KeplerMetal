# Partial threadgroups: reference and native compiler boundary

The existing scoped CPU ICB accepts only thread grids divisible by the requested local dimensions. Partial groups are still refused. This investigation documents what a correct extension must preserve; **it does not implement or enable partial dispatch on the GTX**, change any driver, or establish a performance gain. The [previous GPU qualification](UNIFORM_THREAD_ICB.md) applies to aligned grids only.

## Independent Apple Metal reference

On an Apple M1 Max with macOS 27.2 (26B118), SDK 27.0, a native public Metal program used `dispatchThreads` in two cases: a 33-thread 1D grid with a nominal group of 32, and an 11 × 7 × 5 grid with a nominal group of 4 × 4 × 3. Each thread reported global, group and local coordinates, linear index, grid and group counts, actual and requested group sizes, plus a value shared through a threadgroup barrier. A counter and memory guards were checked. Two serialized cohorts of three fresh signed processes each produced **836 checked GPU threads and 26,752 checked uint32 values**, with **98,816 untouched bytes** in the two separate no-dispatch controls. Each cohort also checks its own output guards. The 3D case contains eight different actual group shapes. The last 1D group contains one thread while `dispatch_threads_per_threadgroup` remains 32.

This corroborates the distinction between the actual group size and the requested size for these shaders; Metal grid coordinates and other builtins must likewise remain correct. Apple describes smaller groups at the grid edge in its [threadgroup sizing guidance](https://developer.apple.com/documentation/metal/calculating-threadgroup-and-grid-sizes?changes=_1); see also the [Metal Shading Language specification](https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf) for the builtins. These are reference executions on Apple Silicon, **not evidence of Kepler execution or support**. The barrier witness tests a particular local-memory exchange, not every synchronization pattern.

The source SHA-256 is `2a503c7a0d22431b4c5d251171b21dc7027519b8c2320d776c23ae3824eedcce`; the ad-hoc signed M1 executable SHA-256 is `2c1d13092feab482a654d718e19e14cc4ab631aac5662db42e618cf6e9170ceb`. Raw output, manifests and the signed executable are retained in the local laboratory, not redistributed. The [audit](partial-grid-research-validation.json) records both manifest hashes. `verify_partial_grid_m1.py` checks every reported field, counters, controls, source and binary hashes, signatures and process statuses; the independent geometry planner is cross-checked against all reference threads.

## Native NVIDIA compiler observation on the iMac

Two fresh isolated processes constructed the existing `depth0` and `grid_coordinates` compute pipelines using the currently pinned NVIDIA driver, with a process-local observer around `NVMTLFunctionVariant` construction. The observer restores the method and **does not dispatch either shader**. The driver file on disk had SHA-256 `e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645`; this does not independently establish the bytes of loaded driver memory. Each container was extracted and independently re-disassembled with the locally built `envydis`; both listings had zero unknown annotations.

For the *specific* 256-byte `depth0` program, the checked disassembly starts with `tidx`, `ctaidx`, and the equivalent of `ctaidx * c1[0x6f0] + tidx + c1[0x710]`. The 1,152-byte `grid_coordinates` program refers to all three CTA coordinates, `c1[0x710..0x718]` and additional values `c1[0x730..0x738]`. This is static evidence of compiler inputs for these exact shaders, not a complete interpretation of their ABI. Program and disassembly hashes and execution-manifest hashes appear in the audit. Neither nonzero origins, group-ID adjustment, group-size builtins, nor partial groups were executed on the GTX. The observer's pilot produced no complete manifest after a launcher import error; its child exited normally and the reservation was terminal. It is excluded from these two final observations.

## CPU-only geometry model

`bridge/tools/partial_grid_plan.py` splits a grid into at most eight disjoint rectangular regions from each dimension's quotient and remainder. It records the logical group base, thread origin, physical group counts, actual group dimensions, nominal dimensions and original grid. Exhaustive CPU tests cover 8,000 small shapes; the audit also compares every thread in both real M1 reference cohorts. It deliberately reports `encoder_implemented: false` and `safe_to_dispatch: false`.

A geometric split alone is insufficient: the native shader must observe correct group IDs, grid sizes, actual **and** requested sizes and barrier behavior. Separate submissions can also change scheduling or progress of cross-group interactions. Offsets in the model are not qualified private packet fields. No untested packet should be submitted to the display GPU.

## Reproduction

Run the portable tests and the example geometry on the iMac:

```sh
python3 -m unittest discover -s tests -p 'test_partial_grid*.py' -v
python3 bridge/tools/partial_grid_plan.py --grid 11 7 5 --local 4 4 3 --max-invocations 385
```

For the native observation, provide the locally retained, hash-pinned libraries and source, and an existing `envydis` executable. `LAB` is the common Kepler laboratory reservation root; all result paths must be new. This constructs pipelines but does not submit a shader. The exact machine profile is checked before and after:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
python3 bridge/tools/partial_grid_capture.py build --out "$LAB/results/partial-build-new" \
  --control /path/to/control_flow.metallib --control-source /path/to/control_flow.metal \
  --grid /path/to/cpu_icb_grid3d.metallib --envydis /path/to/envydis
for function in depth0 grid_coordinates; do
  python3 bridge/tools/partial_grid_capture.py run --build "$LAB/results/partial-build-new" \
    --out "$LAB/results/partial-${function}-new" --reservation-root "$LAB" --function "$function" || break
done
```

The capture builder rejects mismatched libraries or shader sources. Its signed per-process runner uses the shared reservation and preserves the local container and listing. The cohort audit additionally pins exact native program hashes, so a different compiler result requires new analysis, not a silent repin.

On a separate authorized Apple Silicon reference machine, transfer `bridge/tools/partial_grid_m1_reference.mm` as `reference.mm` and `bridge/tools/partial_grid_m1_runner.py` as `runner.py` into a fresh local directory; verify both transfer hashes. There, build and sign `reference` with the host SDK, then run the two cohorts sequentially, substituting the locally computed source and signed-executable hashes:

```sh
xcrun clang++ -arch arm64 -O2 -std=c++17 -fobjc-arc reference.mm -framework Foundation -framework Metal -o reference
codesign --force --sign - reference
codesign --verify --strict reference
shasum -a 256 reference.mm reference runner.py
python3 runner.py --root "$PWD" --out qualified-01 --source-sha SOURCE_SHA256 --binary-sha SIGNED_BINARY_SHA256
python3 runner.py --root "$PWD" --out qualified-02 --source-sha SOURCE_SHA256 --binary-sha SIGNED_BINARY_SHA256
```

Transfer the complete reference directory back and check transfer hashes. From the project checkout, with fresh capture result paths and the local M1 reference root:

```sh
python3 bridge/tools/verify_partial_grid_m1.py /path/to/reference-root --check-current --cohort qualified-01
python3 bridge/tools/verify_partial_grid_m1.py /path/to/reference-root --check-current --cohort qualified-02
python3 bridge/tools/audit_partial_grid_research.py /path/to/depth-capture /path/to/grid-capture /path/to/reference-root
```

The audit pins the captured native code hashes and expects the same source and runner as this checkout. It compares source, manifest and execution evidence and independently checks the geometry. Its JSON is a sanitized summary, not a substitute for the retained raw evidence.

## Next qualification boundary

First determine, with a narrowly guarded process-local experiment and existing certified submission machinery, whether the pinned native shaders can read nonzero coordinate origins and still produce the correct output on the GTX. Separately qualify group IDs, logical group counts, actual versus nominal dimensions and local-memory barriers. The approach must preserve resource ownership and progress and reject unsupported shaders/geometry; semantic equivalence across segmented submissions remains open. Only after those proofs should the scoped ICB's current refusal be reconsidered. Native Apple ICB ABI and transparent integration into ordinary applications remain separate work.
