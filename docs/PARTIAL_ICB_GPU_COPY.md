# GPU-timeline copy of one partial project ICB command

The opted-in project ICB adapter now handles one prepared partial-grid command through the scoped Metal blit selector `copyIndirectCommandBuffer:sourceRange:destination:destinationIndex:`. A partial grid is represented by several native resident descriptors. The adapter issues one GPU buffer blit for each descriptor, retains both sets of records and their resources, and executes the destination after a checked predecessor relationship. This is a process-local project ICB, not Apple's native ICB object or a general GPU-generated-command implementation.

Both the existing partial-grid opt-in and `enableExperimentalPartialGPUCopyWithError:` are required. Prepare the source and destination slots with `prepareExperimentalPartialGPUCopyCommand:index:error:` before adapting the blit encoder. Preparation can submit and wait for bounded initialization/NOP/blit work but dispatches no user shader. The copy accepts one occupied source and destination with the same certified pipeline, registration and grid/local geometry, no prior copied/generated/reusable state, nonoverlapping descriptor allocations and at most **eight** physical regions. The scope, queue, retained uncommitted command buffer, source/destination envelopes and descriptor owners are checked before blits are encoded. More than eight regions is refused before materialization. The CPU shadow of the destination is updated, while execution uses the GPU-copied descriptors. The caller must synchronize CPU mutation and resource contents; a failed encode requires discarding the uncommitted command buffer.

The destination is protected from CPU snapshot overwrite until reset. It can be executed on a serial encoder later in the same recording command buffer, or in a not-yet-enqueued command buffer after the copy buffer is committed on the same queue. A separate consumer before the copy buffer is committed is refused. Chained copies, mixed/multiple slots, GPU-selected source commands, cross-queue ordering, arbitrary shaders and complete Metal ICB semantics remain unqualified. Mutating the copied destination before completion is outside the caller contract. The tested source slot may be reset after encoding because its records and resources are retained.

## GTX qualification

Twelve signed, terminal, nonoverlapping hosts test a 96-thread 1D case with two regions and a 385-thread 3D case with eight regions. Each case has a no-user-dispatch preparation, a native destination baseline, and two executions each for same-buffer and separate-buffer ordering. The eight copied executions submit **40 descriptor blits and 1,924 logical shader invocations**, producing **7,696 exact uint32 values**. Two baselines check another 481 invocations. The destination baseline writes its own output; after GPU copy the destination writes the source command's output and parameters, while the original destination output stays unchanged. Independent CPU checks cover full output, input and guard buffers and both counters.

Every host rejects disabled preparation, unprepared copy, mismatched geometry and the over-eight-region preparation; the latter refuses before materialization. Copied cases reject CPU snapshot overwrite, and four separate-buffer cases reject an uncommitted predecessor. Preparation encodes ten additional blits in uncommitted buffers; those ten are **not** included in the submitted-blit count. Six further same-runtime regression hosts test CPU snapshots, barriers and uniform grids. The [audit](partial-gpu-copy-validation.json) rechecks all 18 hosts, source and artifact identities, signatures, original GPU receipts and CPU oracles. The [mutation checks](partial-gpu-copy-mutation.json) reject seven altered evidence cases; the unchanged copy passes. A separate source rebuild has seven identical object members; that rebuild itself was not run on the GPU. The 31 targeted CPU tests pass.

An initial exploratory build passed both GPU shapes before the geometry and region-limit controls were added. Those runs remain in the local lab and are excluded from this final cohort. No system driver, framework, OCLP or firmware was modified; no performance gain is claimed.

## Reproduction

Use a pinned local `STENCIL`, `WIDE`, `GRIDLIB`, common reservation root `LAB` and current GTX registry ID `RID` as in [the prior snapshot qualification](PARTIAL_ICB_SNAPSHOT.md). Choose fresh paths; do not retry an unresolved process. No vendor binaries are distributed.

```sh
set -e
python3 tools/build_from_source.py --out build/partial-gpu-copy-new
ARCHIVE="$PWD/build/partial-gpu-copy-new"
python3 bridge/tools/partial_gpu_copy.py build --out "$LAB/results/partial-gpu-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do
  for mode in prepare native same separate; do
    python3 bridge/tools/partial_gpu_copy.py run --build "$LAB/results/partial-gpu-build-new" --out "$LAB/results/partial-gpu-$mode$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
  done
  for mode in same separate; do
    python3 bridge/tools/partial_gpu_copy.py run --build "$LAB/results/partial-gpu-build-new" --out "$LAB/results/partial-gpu-$mode-repeat$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
  done
done
python3 bridge/tools/partial_snapshot.py build --out "$LAB/results/partial-gpu-snapshot-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do python3 bridge/tools/partial_snapshot.py run --build "$LAB/results/partial-gpu-snapshot-build-new" --out "$LAB/results/partial-gpu-snapshot$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID"; done
python3 bridge/tools/partial_chain_barrier.py build --out "$LAB/results/partial-gpu-barrier-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
for n in 0 6; do python3 bridge/tools/partial_chain_barrier.py run --build "$LAB/results/partial-gpu-barrier-build-new" --out "$LAB/results/partial-gpu-barrier$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID"; done
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/partial-gpu-uniform-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
for form in groups threads; do python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/partial-gpu-uniform-build-new" --out "$LAB/results/partial-gpu-uniform-$form-new" --reservation-root "$LAB" --mode execute --form "$form" --registry-id "$RID"; done
python3 tools/build_from_source.py --out build/partial-gpu-copy-rebuild-new
python3 bridge/tools/audit_partial_gpu_copy.py --copy \
  "$LAB/results/partial-gpu-prepare0-new" "$LAB/results/partial-gpu-native0-new" "$LAB/results/partial-gpu-same0-new" "$LAB/results/partial-gpu-same-repeat0-new" "$LAB/results/partial-gpu-separate0-new" "$LAB/results/partial-gpu-separate-repeat0-new" \
  "$LAB/results/partial-gpu-prepare3-new" "$LAB/results/partial-gpu-native3-new" "$LAB/results/partial-gpu-same3-new" "$LAB/results/partial-gpu-same-repeat3-new" "$LAB/results/partial-gpu-separate3-new" "$LAB/results/partial-gpu-separate-repeat3-new" \
  --snapshot "$LAB/results/partial-gpu-snapshot0-new" "$LAB/results/partial-gpu-snapshot3-new" \
  --barrier "$LAB/results/partial-gpu-barrier0-new" "$LAB/results/partial-gpu-barrier6-new" \
  --uniform "$LAB/results/partial-gpu-uniform-groups-new" "$LAB/results/partial-gpu-uniform-threads-new" \
  --current-source-build "$PWD/build/partial-gpu-copy-rebuild-new" --out "$LAB/results/partial-gpu-audit-new.json"
python3 bridge/tools/mutate_partial_gpu_copy.py --same "$LAB/results/partial-gpu-same0-new" --separate "$LAB/results/partial-gpu-separate0-new" --prepare "$LAB/results/partial-gpu-prepare0-new"
python3 -m unittest discover -s tests -p 'test_partial*.py' -v
```

The common reservation coordinates participating test runners, not WindowServer or unrelated GPU processes. Proprietary binaries and raw captures stay in the lab.
