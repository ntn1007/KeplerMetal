# Experimental bounded partial-grid dispatch in the project ICB

A later qualification added a second exact read/write buffer shader; see [the stencil extension](PARTIAL_ICB_BUFFER_STENCIL.md). This document describes the original barrier-shader cohort and contract.

The explicitly enabled, process-local CPU ICB adapter now decomposes **bounded nonuniform 1D, 2D and 3D grids** for the exact registered `partial_builtin_barrier` shader and manifest. This expands the earlier [fixed-grid experiment](PARTIAL_ICB_FIXED_PROFILE.md). It is an experimental adapted-application path: it is not arbitrary-shader support, the native Apple ICB ABI, a system driver update, a Metal version upgrade, or transparent integration into unmodified applications.

After installing the scope with the [certified wide-shader library and manifest](../bridge/src/partial_wide_barrier.json), the caller must explicitly call `enableExperimentalPartialGridWithError:`. Then the project command's `concurrentDispatchThreads:threadsPerThreadgroup:` accepts nonzero **partial** dimensions if all these conditions hold:

- Each grid and nominal local dimension is at most 1,023; grid volume is at most 1,024 and nominal group volume is at most 128.
- The deterministic CPU planner can represent the grid in at most 16 regions, each containing at most 128 physical invocations. A grid can satisfy the volume limits yet still be refused if its decomposition exceeds 16 regions; for example, the CPU contract test rejects `(3,21,15)` with local `(2,5,7)`.
- The exact certified pipeline, manifest, reflected ABI and device profile are retained. The execution range contains exactly one command, on a serial compute encoder belonging to an uncommitted retained command buffer on the scope queue.
- Bindings 0 and 1 are distinct 16,512-byte Private buffers at offset 64; binding 2 is a distinct 132-byte Private buffer at offset 64; binding 3 is a distinct 1,536-byte Shared buffer at offset 256. They belong to the same device. The adapter rejects zero, overflowing or overlapping GPU address ranges, including overlaps between distinct buffer objects.

Fully divisible grids continue through the original uniform path and its own manifest limits; this opt-in does not relax those limits. CPU snapshot copy, GPU-selected command export, mixed ranges, concurrent encoders and unqualified resources remain refused. Callers must externally synchronize command mutation and preserve resource contents through completion. If encoding raises an exception or reports an error, discard that uncommitted command buffer rather than submitting it. The shader source defines the output, counter and parameter layout.

For each partial grid the planner partitions full and edge groups, then tiles regions so each native record stays within the certified 128-invocation bound. The adapter materializes and caches those records, initializes their private QMDs and constants, then uses the existing serialized resident-launch transport. Rebinding or reset invalidates the cache. Preparation can submit and wait for native NOP and blit work but does not execute the user shader. The scope's retained command buffer owns the necessary records until completion. Region launches are serialized: this can change cross-group scheduling relative to one native dispatch, so the exact shader is certified independently and arbitrary shaders are refused. No global framework, driver or OCLP changes are made.

## Qualification and limits

The actual C++ planner is tested against an independently enumerated thread set for **11,520 small geometries**, checking complete coverage, no duplicates, logical group IDs, actual group sizes, per-record limits and failure boundaries. Its GPU-address range helper has CPU tests for adjacency, overlap, zero and overflow. The GPU cohort exercises same-object alias refusal; it does not separately demonstrate distinct heap-backed objects overlapping in GPU memory.

On the GTX 880M, 13 distinct partial geometries were tested across 17 fresh execution processes, plus two preparation processes. They include the original 3D grid, the 191-thread 1D grid, a group larger than the grid, 1,023-thread X/Y/Z cases, 2D and 3D cases requiring multiple physical tiles, a one-thread edge with nominal size 128, and a 16-region boundary case. The original 3D and 1,023-thread X cases were each repeated in three processes; other shapes were tested once. Each execution process runs four full outputs covering first materialization, cache reuse, rebinding, and reset/re-encoding with scope restoration before commit. Across the processes, **68 user command buffers, 36,848 GPU invocations and 294,784 uint32 output values** match an independent CPU oracle. Pre-commit output and suppressed-launch controls remain untouched. There are **154 observations across nine refusal cases**, including disabled opt-in, invalid dimensions, alias, short buffer, mixed range, copy attempted ordinary-resident export, and a grid needing more than 16 regions.

The [main audit](partial-general-api-validation.json) checks signatures, serialized hosts, frozen sources, profile, reported resident streams, all output/guard bytes and repeated results; the [additional-axis audit](partial-general-extra-validation.json) covers the Y, Z and further 2D/3D tiling cases, and the [boundary audit](partial-general-limit-validation.json) covers exactly 16 regions and rejection above the limit. It matches 16 output files against prior GPU prototypes. For the original 3D case, **194,040 metadata components** agree with two previously captured M1 Max references. Those reference captures are not new M1 runs or evidence of GTX execution; their barrier witnesses are independently checked, not directly compared.

The same new runtime passes two GTX uniform-group/thread regression hosts: **37,264 invocations, 298,112 values and 180 paired data files**. These results are bounded samples, not GPU qualification of every accepted geometry, every synchronization pattern, every shader or the full Metal API. No speedup is claimed.

## Reproduction

Use a current GTX registry ID `RID`, the shared laboratory reservation root `LAB`, the pinned shader library `WIDE`, the previously qualified uniform library `GRIDLIB`, earlier reference paths `FIXED3D` and `MANUAL1D`, and the two-cohort M1 reference directory `M1_ROOT`. All output directories must be fresh. The build refuses a changed source, SDK, shader or system profile rather than silently repinning.

```sh
python3 tools/build_from_source.py --out build/partial-general-new
ARCHIVE="$PWD/build/partial-general-new"
python3 bridge/tools/partial_general_api.py build --out "$LAB/results/general-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
python3 bridge/tools/partial_general_api.py run --build "$LAB/results/general-build-new" --out "$LAB/results/general-prepare-new" --reservation-root "$LAB" --mode prepare --case-index 0 --registry-id "$RID"
for n in 0 1 2 3 4 5 6 7; do
  python3 bridge/tools/partial_general_api.py run --build "$LAB/results/general-build-new" --out "$LAB/results/general-case-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
for n in 0 6; do
  for rep in 1 2; do
    python3 bridge/tools/partial_general_api.py run --build "$LAB/results/general-build-new" --out "$LAB/results/general-case-$n-repeat-$rep-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
  done
done
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/general-uniform-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
for form in groups threads; do
  python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/general-uniform-build-new" --out "$LAB/results/general-uniform-$form-new" --reservation-root "$LAB" --mode execute --form "$form" --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_general_api.py "$LAB/results/general-prepare-new" \
  "$LAB/results/general-case-0-new" "$LAB/results/general-case-1-new" "$LAB/results/general-case-2-new" "$LAB/results/general-case-3-new" \
  "$LAB/results/general-case-4-new" "$LAB/results/general-case-5-new" "$LAB/results/general-case-6-new" "$LAB/results/general-case-7-new" \
  "$LAB/results/general-uniform-groups-new" "$LAB/results/general-uniform-threads-new" "$FIXED3D" "$MANUAL1D" "$M1_ROOT" \
  "$LAB/results/general-case-0-repeat-1-new" "$LAB/results/general-case-0-repeat-2-new" "$LAB/results/general-case-6-repeat-1-new" "$LAB/results/general-case-6-repeat-2-new"
python3 bridge/tools/partial_general_extra.py build --out "$LAB/results/general-extra-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
for n in 0 1 2 3; do
  python3 bridge/tools/partial_general_extra.py run --build "$LAB/results/general-extra-build-new" --out "$LAB/results/general-extra-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_general_extra.py "$LAB/results/general-extra-0-new" "$LAB/results/general-extra-1-new" "$LAB/results/general-extra-2-new" "$LAB/results/general-extra-3-new" "$LAB/results/general-uniform-threads-new"
python3 bridge/tools/partial_general_limit.py build --out "$LAB/results/general-limit-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
for mode in prepare execute; do
  python3 bridge/tools/partial_general_limit.py run --build "$LAB/results/general-limit-build-new" --out "$LAB/results/general-limit-$mode-new" --reservation-root "$LAB" --mode "$mode" --case-index 0 --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_general_limit.py "$LAB/results/general-limit-prepare-new" "$LAB/results/general-limit-execute-new" "$LAB/results/general-extra-3-new"
```

The exact shader/library and historical references are generated or retained locally; proprietary binaries are not distributed. Treat changed SDK output or driver profiles as new experiments requiring requalification.
