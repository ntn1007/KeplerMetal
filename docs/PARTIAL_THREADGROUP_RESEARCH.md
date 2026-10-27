# Partial threadgroups: reference and native compiler boundary

The scoped CPU ICB accepts aligned grids and, through a separately enabled [bounded-profile experiment](PARTIAL_ICB_BOUNDED_PROFILE.md), partial grids for the certified shader and resource envelope. Other partial groups remain refused. The investigations below document the evidence and limits; they do not establish general partial dispatch, change any driver, or establish a performance gain. The [previous GPU qualification](UNIFORM_THREAD_ICB.md) applies to aligned grids only.

## Independent Apple Metal reference

On an Apple M1 Max with macOS 27.2 (26B118), SDK 27.0, a native public Metal program used `dispatchThreads` in two cases: a 33-thread 1D grid with a nominal group of 32, and an 11 × 7 × 5 grid with a nominal group of 4 × 4 × 3. Each thread reported global, group and local coordinates, linear index, grid and group counts, actual and requested group sizes, plus a value shared through a threadgroup barrier. A counter and memory guards were checked. Two serialized cohorts of three fresh signed processes each produced **836 checked GPU threads and 26,752 checked uint32 values**, with **98,816 untouched bytes** in the two separate no-dispatch controls. Each cohort also checks its own output guards. The 3D case contains eight different actual group shapes. The last 1D group contains one thread while `dispatch_threads_per_threadgroup` remains 32.

This corroborates the distinction between the actual group size and the requested size for these shaders; Metal grid coordinates and other builtins must likewise remain correct. Apple describes smaller groups at the grid edge in its [threadgroup sizing guidance](https://developer.apple.com/documentation/metal/calculating-threadgroup-and-grid-sizes?changes=_1); see also the [Metal Shading Language specification](https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf) for the builtins. These are reference executions on Apple Silicon, **not evidence of Kepler execution or support**. The barrier witness tests a particular local-memory exchange, not every synchronization pattern.

The source SHA-256 is `2a503c7a0d22431b4c5d251171b21dc7027519b8c2320d776c23ae3824eedcce`; the ad-hoc signed M1 executable SHA-256 is `2c1d13092feab482a654d718e19e14cc4ab631aac5662db42e618cf6e9170ceb`. Raw output, manifests and the signed executable are retained in the local laboratory, not redistributed. The [audit](partial-grid-research-validation.json) records both manifest hashes. `verify_partial_grid_m1.py` checks every reported field, counters, controls, source and binary hashes, signatures and process statuses; the independent geometry planner is cross-checked against all reference threads.

## Native NVIDIA compiler observation on the iMac

Two fresh isolated processes constructed the existing `depth0` and `grid_coordinates` compute pipelines using the currently pinned NVIDIA driver, with a process-local observer around `NVMTLFunctionVariant` construction. The observer restores the method and **does not dispatch either shader**. The driver file on disk had SHA-256 `e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645`; this does not independently establish the bytes of loaded driver memory. Each container was extracted and independently re-disassembled with the locally built `envydis`; both listings had zero unknown annotations.

For the *specific* 256-byte `depth0` program, the checked disassembly starts with `tidx`, `ctaidx`, and the equivalent of `ctaidx * c1[0x6f0] + tidx + c1[0x710]`. The 1,152-byte `grid_coordinates` program refers to all three CTA coordinates, `c1[0x710..0x718]` and additional values `c1[0x730..0x738]`. This is static evidence of compiler inputs for these exact shaders, not a complete interpretation of their ABI. Program and disassembly hashes and execution-manifest hashes appear in the audit. At the time of this capture, nonzero origins, group-ID adjustment and partial groups had not been executed on the GTX. Later bounded origin, assembly and opt-in integration experiments are documented below. The observer's pilot produced no complete manifest after a launcher import error; its child exited normally and the reservation was terminal. It is excluded from these two final observations.

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

The bounded origin experiment below qualifies one native shader and selected group-ID shifts. The later edge-builtins experiment exercises selected logical group counts and actual dimensions. The later builtin/barrier witness directly reports the nominal and grid builtins for selected cases. The later wide-group witness covers selected groups spanning multiple warps. Isolate field causality and qualify complete decompositions separately. The approach must preserve resource ownership and progress and reject unsupported shaders/geometry; semantic equivalence across segmented submissions remains open. Only after those proofs should the scoped ICB's current refusal be reconsidered. Native Apple ICB ABI and transparent integration into ordinary applications remain separate work.

## Follow-up: bounded nonzero origins on the GTX 880M

A separate process-local probe uses the existing scope-owned `grid_coordinates` shader, its pinned library and the already qualified resident descriptor/launch transport. It does **not** alter the native instruction stream or construct a new GPU packet. After the normal resident preparation, a Metal blit changes only the three origin values at offsets `0x710`, `0x714`, `0x718` in that record's dedicated 64 KiB constant buffer. Before launching, the full buffer is checked against the untouched baseline plus exactly those 12 bytes, and the whole resident descriptor is checked against the baseline. Both are read back and compared again after every launch. The output buffers and all output indexes are bounded by the shader's 1,024-element limit.

One preparation process and three independent execution processes completed serially under the common host reservation. Each execution has a suppressed-launch control, four zero-origin launches (including two repetitions of the 1D baseline), and three nonzero cases: X origin `(8,0,0)` with group size `(4,1,1)`, Y origin `(0,4,0)` with group size `(4,2,1)`, and Z origin `(0,0,4)` with group size `(4,2,2)`. Across all three hosts, **21 user launches / 1,032 invocations / 8,256 uint32 coordinate and geometry values** matched the independent CPU oracle. The oracle checks the invocation counters and every byte of the output buffers, including unwritten regions and guards; three suppressed-launch controls remain untouched. Matching coordinate and geometry output hashes repeat across the three processes. The [cohort audit](partial-origin-validation.json) records exact source, archive, library, host, driver-file and manifest hashes. The raw buffers, constant snapshots, descriptors and signed hosts remain in the local lab.

For these aligned origins and this exact shader, the observed global coordinates and group IDs include the tested offsets; local positions, physical group counts and local dimensions retain their expected values. The experiment does **not** establish arbitrary-origin correctness, nonuniform groups, logical grid or group counts for a larger decomposed dispatch, other shaders, global application integration, or performance. It also does not prove that the installed driver was repaired. The existing refusal of partial groups is unchanged.

To reproduce, start from the public archive and hash-pinned library used by the aligned-grid qualification, and use a fresh result directory for every host. Replace `RID` with the currently observed GTX registry ID; the common reservation root must be the same one used by all GTX probes.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
ARCHIVE='/path/to/qualified-public-source-archive'
GRIDLIB='/path/to/cpu_icb_grid3d.metallib'
RID=REPLACE_WITH_CURRENT_REGISTRY_ID
python3 bridge/tools/partial_origin.py build --out "$LAB/results/origin-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
python3 bridge/tools/partial_origin.py run --build "$LAB/results/origin-build-new" --out "$LAB/results/origin-prepare-new" --reservation-root "$LAB" --mode prepare --registry-id "$RID"
for run in 1 2 3; do
  python3 bridge/tools/partial_origin.py run --build "$LAB/results/origin-build-new" --out "$LAB/results/origin-execute-new-$run" --reservation-root "$LAB" --mode execute --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_origin.py "$LAB/results/origin-prepare-new" "$LAB/results/origin-execute-new-1" "$LAB/results/origin-execute-new-2" "$LAB/results/origin-execute-new-3"
```

The builder checks source/archive, SDK, library, manifest and machine profile. The runner freezes inputs, checks the same profile, uses a separately signed host and the common reservation, and invokes the independent raw-data verifier. The auditor checks four terminal serialized processes and signatures. Unknown drivers or assets are refused, not automatically repinned.

## Follow-up: edge-group builtins on the GTX

A further isolated experiment uses the same certified shader and resident launch mechanism. Each actual launch is a **single, ordinary physical threadgroup**, with size smaller in one dimension than a separately supplied nominal size. The probe changes the origin, nominal size, logical group count and candidate logical-grid fields **together** in the record's private constant buffer; these changes do not establish the individual causal role of each field. No native command or shader bytes are patched. Its complete 64 KiB constant buffer and 4 KiB descriptor are read back and checked before and after launch.

| Case | Actual physical group | Supplied nominal size | Origin | Supplied logical group counts | Observed group ID |
| --- | --- | --- | --- | --- | --- |
| X edge | `(3,1,1)` | `(4,1,1)` | `(8,0,0)` | `(3,1,1)` | `(2,0,0)` |
| Y edge | `(4,1,1)` | `(4,2,1)` | `(0,4,0)` | `(2,3,1)` | `(0,2,0)` |
| Z edge | `(4,2,1)` | `(4,2,2)` | `(0,0,4)` | `(2,2,3)` | `(0,0,2)` |

One preparation and three fresh serialized execution processes qualified **18 launches, 90 shader invocations and 720 checked coordinate/geometry values**, with three suppressed-launch controls. Each process includes an unmodified physical-geometry control for each edge case. Independent CPU verification checks counters, all output bytes and guards, group and local coordinates, actual local size and reported group counts. The three processes produce matching output hashes. The [audit](partial-nominal-validation.json) additionally checks native QMD dimensions, builtin baseline fields, the reported resident select/launch/wait stream hashes, signatures, source/build fingerprints and terminal reservations.

The shader computes its own output index using `groups * actualLocal`; this is **not** a validated linear index for the full logical Metal grid. Although the candidate logical-grid field is changed, this shader does not report `threads_per_grid`. It does not report `dispatch_threads_per_threadgroup` either. Thus the test shows that selected edge metadata produces the expected outputs for this shader, **not** that all Metal builtins or arbitrary shaders work. No group barrier is exercised, at this stage no complete multi-region dispatch was implemented, and the partial-ICB refusal remained in place. Further isolate field causality with controls and use a shader explicitly reporting nominal/grid sizes and barriers before integration.

Reproduce with the same pinned archive, library, current registry ID and common reservation root as the origin experiment; output directories must be new:

```sh
python3 bridge/tools/partial_nominal.py build --out "$LAB/results/nominal-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
python3 bridge/tools/partial_nominal.py run --build "$LAB/results/nominal-build-new" --out "$LAB/results/nominal-prepare-new" --reservation-root "$LAB" --mode prepare --registry-id "$RID"
for run in 1 2 3; do
  python3 bridge/tools/partial_nominal.py run --build "$LAB/results/nominal-build-new" --out "$LAB/results/nominal-execute-new-$run" --reservation-root "$LAB" --mode execute --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_nominal.py "$LAB/results/nominal-prepare-new" "$LAB/results/nominal-execute-new-1" "$LAB/results/nominal-execute-new-2" "$LAB/results/nominal-execute-new-3"
```

## Follow-up: directly reported builtins and a local barrier

A new [bounded MSL shader](../bridge/src/partial_builtin_barrier.metal) reports global, local and group coordinates, logical group counts, `threads_per_threadgroup`, `dispatch_threads_per_threadgroup` and `threads_per_grid`. Each thread writes a value to threadgroup memory, executes `threadgroup_barrier(mem_flags::mem_threadgroup)`, then reports the value written by its next thread. The 32-element local array and each dispatched group are explicitly bounded; the shader checks its output index against a 1,024-element buffer.

A separate construction-only inspection reflects four expected buffers and shows 256 bytes of static threadgroup memory and 22 registers in the observed NVIDIA QMD. It does not commit GPU work. Its signed process, locally built AIR/library and source are tied to the later cohort by hashes in the [audit](partial-builtin-validation.json). An earlier construction pilot exited normally, but its launcher could not write a manifest because a helper was not in the expected directory; it is excluded from the audit.

Three fresh execution processes each run physical groups of 3, 4 and 8 threads. Each size has a normal zero-origin control and an edge case with a distinct nominal size, logical grid and group count, as in the preceding table. Across them, **18 launches, 90 invocations and 720 reported uint32 fields** match an independent CPU oracle; three suppressed-launch controls remain untouched. The oracle compares every output byte, guard and counter, including each thread's neighbor witness. It also verifies full constant and descriptor snapshots before and after execution. Output hashes repeat across processes. The audit verifies native QMD geometry, the reported resident command-stream hashes, signed hosts, serialized reservations and source/library provenance.

These are **single-group, within-one-warp examples**: successful output with the barrier present does not demonstrate that the barrier was necessary, nor establish cross-warp synchronization or the progress of a split dispatch. Several metadata fields still change together. This does not implement partial Metal dispatch, establish arbitrary shader correctness or modify the installed driver. A complete integration must separately cover cross-warp and larger groups, field-isolating controls, multiple adjacent regions, resource lifetimes and regressions before relaxing the current rejection. No performance claim is made.

Reproduce with the same `LAB`, `ARCHIVE` and `RID` variables as above. The shader build requires Metal 2.3; a different toolchain may produce a library with a different hash and will be refused rather than silently repinned. All directories must be fresh. The source snapshot and exact driver profile are checked by the builders.

```sh
python3 bridge/tools/partial_builtin_pipeline.py build --out "$LAB/results/builtin-pipeline-build-new"
python3 bridge/tools/partial_builtin_pipeline.py run --build "$LAB/results/builtin-pipeline-build-new" --out "$LAB/results/builtin-pipeline-new" --reservation-root "$LAB" --registry-id "$RID"
python3 bridge/tools/partial_builtin_run.py build --out "$LAB/results/builtin-run-build-new" --archive "$ARCHIVE" --metallib "$LAB/results/builtin-pipeline-build-new/assets/shader.metallib"
python3 bridge/tools/partial_builtin_run.py run --build "$LAB/results/builtin-run-build-new" --out "$LAB/results/builtin-prepare-new" --reservation-root "$LAB" --mode prepare --registry-id "$RID"
for run in 1 2 3; do
  python3 bridge/tools/partial_builtin_run.py run --build "$LAB/results/builtin-run-build-new" --out "$LAB/results/builtin-execute-new-$run" --reservation-root "$LAB" --mode execute --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_builtin.py "$LAB/results/builtin-pipeline-new" "$LAB/results/builtin-prepare-new" "$LAB/results/builtin-execute-new-1" "$LAB/results/builtin-execute-new-2" "$LAB/results/builtin-execute-new-3"
```

## Follow-up: multi-warp threadgroup witness

The [wide diagnostic shader](../bridge/src/partial_wide_barrier.metal) expands the local array to 128 words. After a threadgroup barrier, every thread reads the value written by the thread whose linear local index is `(index + 32) % groupSize`. Its exact source, AIR, library, signed host and driver-profile hashes are recorded in the [audit](partial-wide-validation.json). On the usual NVIDIA 32-thread warp mapping, many of these exchanges cross a warp boundary; the observed pipeline reports a 32-thread execution width. The test does not independently trace warp scheduling.

Three serialized, signed processes each execute zero-origin and edge-metadata cases for physical groups of **63**, **56** and **96** threads. Actual and nominal dimensions differ along X, Y and Z respectively in the edge cases; the output buffers are bounded and guards checked. The construction-only pipeline inspection reports 512 bytes of static threadgroup memory and 22 registers. Across the execution processes, **18 launches, 1,290 invocations and 10,320 uint32 outputs** match the independent CPU oracle, with three untouched suppressed-launch controls. The same shader reports global/local/group coordinates, logical group counts, actual and nominal group sizes, and grid size. Complete resident constant buffers and descriptors match their expected before/after snapshots. Each process produces identical output hashes.

This is evidence that the tested shader and barrier produce the expected results on groups larger than one warp. It is not a proof that removing the barrier would fail, that all synchronization patterns are correct, or that arbitrary shader/group sizes work. Origin, grid, nominal size and group-count data still change together. Those individual edge trials use one physical group each. The later assembly experiment joins adjacent regions through two resident launches; native ICB identity, transparent integration and a general Metal dispatch remain unimplemented. No performance gain is claimed.

Reproduce with `LAB`, `ARCHIVE` and `RID` as in the previous section. Use fresh directories; the build pins the original source/toolchain result and the GPU runner uses the shared reservation:

```sh
python3 bridge/tools/partial_wide_pipeline.py build --out "$LAB/results/wide-pipeline-build-new"
python3 bridge/tools/partial_wide_pipeline.py run --build "$LAB/results/wide-pipeline-build-new" --out "$LAB/results/wide-pipeline-new" --reservation-root "$LAB" --registry-id "$RID"
python3 bridge/tools/partial_wide_run.py build --out "$LAB/results/wide-run-build-new" --archive "$ARCHIVE" --metallib "$LAB/results/wide-pipeline-build-new/assets/shader.metallib"
python3 bridge/tools/partial_wide_run.py run --build "$LAB/results/wide-run-build-new" --out "$LAB/results/wide-prepare-new" --reservation-root "$LAB" --mode prepare --registry-id "$RID"
for run in 1 2 3; do
  python3 bridge/tools/partial_wide_run.py run --build "$LAB/results/wide-run-build-new" --out "$LAB/results/wide-execute-new-$run" --reservation-root "$LAB" --mode execute --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_wide.py "$LAB/results/wide-pipeline-new" "$LAB/results/wide-prepare-new" "$LAB/results/wide-execute-new-1" "$LAB/results/wide-execute-new-2" "$LAB/results/wide-execute-new-3"
```

## Follow-up: assembling one bounded logical grid on the GTX

A process-local laboratory client now assembles a **191-thread, one-dimensional logical grid**, with a requested group size of 64. It uses two independently prepared records of the already qualified wide-barrier shader: the first launches two full physical groups of 64, and the second launches one physical group of 63 at logical origin 128. Both records reference the same bounded output and counter buffers. The client sets the logical grid, nominal size, group count and origin in each record's private constant data, then submits their existing resident launch sequence in **one user command buffer**. This is two native launches, not a native Metal nonuniform `dispatchThreads` implementation.

Three fresh execution processes each run a suppressed-launch control, each region alone, then the two-region sequence in both orders. Across them, **six complete 191-thread grids**, six single-region controls and three suppressed-launch controls passed. Including the controls, **18 native launches, 1,719 invocations and 13,752 coordinate, builtin and barrier-witness values** match the independent CPU oracle. Both sequence orders and all three processes produced matching full-output hashes. Every output byte and guard, the counter, both QMD geometries, full resident constant snapshots and the reported command-stream hashes were checked. The [audit](partial-assembly-validation.json) records host, runtime, shader-library, driver-file and process-manifest hashes.

The tested shader sees the expected logical thread and group coordinates, three logical groups, a nominal size of 64, and an actual size of 63 in the edge group. Its per-group barrier witness also matches. This is an important bounded end-to-end experiment for the decomposition, but it still relies on an explicitly adapted client, a single fixed shader and grid, exact-profile resident commands, and serialized launches. It does not establish semantics for arbitrary shaders, cross-group progress or scheduling, arbitrary 2D/3D edges, resource lifetime scenarios, native Apple ICB identity, or transparent ordinary-application integration. In particular, a shader relying on unspecified cross-group concurrency may behave differently when split. At this stage the public scoped ICB still rejected partial `concurrentDispatchThreads`; the later fixed-profile opt-in is documented separately. No system component or driver was changed.

To reproduce, retain the pinned wide shader library and the qualified public archive and use the same `LAB`, `ARCHIVE`, `RID` variables and common host reservation described above. Use new output directories:

```sh
python3 bridge/tools/partial_assembly.py build --out "$LAB/results/assembly-build-new" --archive "$ARCHIVE" --metallib "$LAB/results/wide-pipeline-build-new/assets/shader.metallib"
python3 bridge/tools/partial_assembly.py run --build "$LAB/results/assembly-build-new" --out "$LAB/results/assembly-prepare-new" --reservation-root "$LAB" --mode prepare --registry-id "$RID"
for run in 1 2 3; do
  python3 bridge/tools/partial_assembly.py run --build "$LAB/results/assembly-build-new" --out "$LAB/results/assembly-execute-new-$run" --reservation-root "$LAB" --mode execute --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_assembly.py "$LAB/results/assembly-prepare-new" "$LAB/results/assembly-execute-new-1" "$LAB/results/assembly-execute-new-2" "$LAB/results/assembly-execute-new-3"
```

## Follow-up: eight-region 3D grid and M1 reference comparison

A separate fixed adapted client assembles a logical **11 × 7 × 5 grid** with nominal group size **4 × 4 × 3**. Its eight independently prepared resident records cover the full interior, three faces, three edges and the corner. The first four records each launch two physical groups; the last four launch one, for twelve physical groups in all. Each record retains its own validated QMD and constant buffer while sharing the bounded output and atomic counter. The eight native launches are submitted in one user command buffer. This remains a fixed project-owned transport experiment, not the native Metal `dispatchThreads` implementation.

Three fresh signed processes each run an untouched suppressed-launch control, all eight regions individually, then the full sequence in forward and reverse order. The three processes cover **six complete 385-thread grids**, 24 single-region controls, three suppressed controls, **72 native launches, 3,465 invocations and 27,720 checked uint32 outputs**. The CPU oracle verifies every coordinate, actual and nominal group size, logical grid and group count, local-memory witness, counter, output byte and guard. Full 64 KiB constants and 4 KiB QMD snapshots are rechecked for every record after every trial. The verifier checks the resident launch-stream hashes and record geometry; the [audit](partial-assembly-3d-validation.json) verifies signatures, serial completion, frozen inputs and matching outputs across both orders and all processes.

The audit also rechecks the two previously captured, native Apple M1 Max reference cohorts for the same logical grid. For each GTX output and each M1 capture it compares all three components of seven metadata fields: global/local/group position, group count, actual size, nominal size and grid size. All **48,510 component comparisons** match. This is a comparison of independently obtained results, not a new M1 run, and the M1 result is not evidence of Kepler GPU execution. The two shaders use different barrier witnesses; those witnesses are checked against their respective CPU oracles, not directly compared.

The outcome qualifies this specific shader and geometry through a process-local adapted client. It does not prove arbitrary Metal shaders, all possible 2D/3D sizes, cross-group forward progress or ordering, performance, native Apple ICB identity or transparent ordinary-application behavior. Region launches are serialized; replacing one dispatch with several launches could change scheduling. At that stage the scoped ICB still rejected partial `concurrentDispatchThreads`; a later fixed-profile opt-in and bounded lifecycle qualification are documented separately. No system driver is changed.

Reproduce using the same pinned wide shader library, public archive, common lab reservation and M1 reference directory described above. Supply the current GTX registry ID and fresh output paths:

```sh
python3 bridge/tools/partial_assembly_3d.py build --out "$LAB/results/assembly-3d-build-new" --archive "$ARCHIVE" --metallib "$LAB/results/wide-pipeline-build-new/assets/shader.metallib"
python3 bridge/tools/partial_assembly_3d.py run --build "$LAB/results/assembly-3d-build-new" --out "$LAB/results/assembly-3d-prepare-new" --reservation-root "$LAB" --mode prepare --registry-id "$RID"
for run in 1 2 3; do
  python3 bridge/tools/partial_assembly_3d.py run --build "$LAB/results/assembly-3d-build-new" --out "$LAB/results/assembly-3d-execute-new-$run" --reservation-root "$LAB" --mode execute --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_assembly_3d.py "$LAB/results/assembly-3d-prepare-new" "$LAB/results/assembly-3d-execute-new-1" "$LAB/results/assembly-3d-execute-new-2" "$LAB/results/assembly-3d-execute-new-3" "$M1_ROOT"
```
