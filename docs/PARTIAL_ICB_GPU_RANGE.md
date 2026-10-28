# GPU-timeline copies of bounded partial command ranges

This page records the earlier qualification. The later [mixed-copy qualification](PARTIAL_ICB_GPU_MIXED_COPY.md) extends its scope.

The process-local, explicitly opted-in project ICB adapter can copy a range of prepared partial-grid commands through the scoped Metal blit selector. It checks the complete range before encoding a blit or mutating the destination CPU shadow, then encodes one Metal buffer copy per physical QMD. Each source/destination pair must have the same certified pipeline, registration and geometry; descriptor allocations across the range must be disjoint. The total is limited to eight physical regions and sixteen retained owners. These are project-owned commands, not native Apple ICBs, a system driver, or general GPU-generated commands.

Enable both the partial-grid feature and `enableExperimentalPartialGPUCopyWithError:`; prepare both endpoints using `prepareExperimentalPartialGPUCopyCommand:index:error:`. Execution on a serial encoder may combine copied partial commands with original qualified partial or uniform commands. Each copied slot requires the same recording command buffer, or a committed predecessor on the same scope queue. Source records and resources survive source reset. Caller synchronization of CPU mutation and resource contents remains required; discard an uncommitted command buffer if encoding throws. Cross-queue dependencies, chained GPU copies, GPU-selected source commands, mixed partial/uniform *copy* ranges and arbitrary shaders remain outside the qualified contract. Owner-count limits can reject ranges with fewer than sixteen launches.

## Qualification on GTX 880M

Three independent 12-process cohorts cover 96-thread 1D and 75-thread 3D producer/consumer cases, with preparation, a native destination baseline and two repetitions each for same-buffer and separately committed same-queue ordering. They exercise a two-command range copied in full, a copied partial followed by an unchanged partial, and a copied partial followed by an unchanged uniform command. Each of the 24 copied executions performs two dependent dispatches; together they produce **4,104 shader invocations**, **16,416 checked 32-bit output values**, and **96 submitted QMD buffer blits**. For mixed cohorts the invocation count includes the unchanged second command. The no-copy baselines and preparations are separate; preparation blits remain uncommitted and are excluded from that total.

CPU oracles check both outputs, inputs, counters and guards. The original destination outputs remain unchanged after full copying; mixed controls verify that the unchanged second command still reads its original inputs. Each cohort includes geometry mismatch, unprepared input, disabled operation and over-eight-region rejection; separate-buffer cases additionally reject a predecessor that has not been committed. A mistaken early limit test expected eight regions to be rejected; the corrected test uses more than eight. That failed exploratory process is retained locally and excluded from the qualification.

The [machine-readable audit](partial-gpu-range-validation.json) rechecks frozen sources, signed hosts, results, resource reservations, nonoverlapping process intervals and seven object members from an independent rebuild. It also includes earlier single-copy, CPU snapshot, barrier and uniform regressions on the same runtime. Seven [offline mutations](partial-gpu-range-mutation.json) are refused while the untouched evidence passes. The full CPU suite reports 500 tests with one skipped. No speedup is claimed; no system components were modified. The reservation coordinates cooperating test runners, not WindowServer or unrelated GPU activity.

## Reproduction

Obtain pinned local `STENCIL`, `WIDE`, `GRIDLIB`, common reservation root `LAB`, and current GTX registry ID `RID` as in [the preceding qualification](PARTIAL_ICB_GPU_COPY.md). Never distribute proprietary files. Run in a checked-out repository with fresh output paths; don't retry while a process or GPU reservation remains unresolved.

```sh
set -e
python3 tools/build_from_source.py --out build/partial-gpu-range-new
ARCHIVE="$PWD/build/partial-gpu-range-new"
for group in range mixed uniform; do
  python3 "bridge/tools/partial_gpu_${group}.py" build --out "$LAB/results/range-$group-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
  for n in 0 3; do
    for mode in prepare native same separate; do
      python3 "bridge/tools/partial_gpu_${group}.py" run --build "$LAB/results/range-$group-build-new" --out "$LAB/results/range-$group-$mode-$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
    done
    for mode in same separate; do
      python3 "bridge/tools/partial_gpu_${group}.py" run --build "$LAB/results/range-$group-build-new" --out "$LAB/results/range-$group-$mode-repeat-$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
    done
  done
done
python3 bridge/tools/partial_gpu_copy.py build --out "$LAB/results/range-single-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do for mode in same separate; do python3 bridge/tools/partial_gpu_copy.py run --build "$LAB/results/range-single-build-new" --out "$LAB/results/range-single-$mode-$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"; done; done
python3 bridge/tools/partial_snapshot.py build --out "$LAB/results/range-snapshot-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do python3 bridge/tools/partial_snapshot.py run --build "$LAB/results/range-snapshot-build-new" --out "$LAB/results/range-snapshot-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID"; done
python3 bridge/tools/partial_chain_barrier.py build --out "$LAB/results/range-barrier-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
for n in 0 6; do python3 bridge/tools/partial_chain_barrier.py run --build "$LAB/results/range-barrier-build-new" --out "$LAB/results/range-barrier-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID"; done
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/range-uniform-reg-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
for form in groups threads; do python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/range-uniform-reg-build-new" --out "$LAB/results/range-uniform-reg-$form-new" --reservation-root "$LAB" --mode execute --form "$form" --registry-id "$RID"; done
python3 tools/build_from_source.py --out build/partial-gpu-range-rebuild-new
python3 bridge/tools/audit_partial_gpu_range.py \
  --range "$LAB"/results/range-range-{prepare,native,same,separate,same-repeat,separate-repeat}-{0,3}-new \
  --mixed "$LAB"/results/range-mixed-{prepare,native,same,separate,same-repeat,separate-repeat}-{0,3}-new \
  --mixed-uniform "$LAB"/results/range-uniform-{prepare,native,same,separate,same-repeat,separate-repeat}-{0,3}-new \
  --single "$LAB"/results/range-single-{same,separate}-{0,3}-new \
  --snapshot "$LAB"/results/range-snapshot-{0,3}-new \
  --barrier "$LAB"/results/range-barrier-{0,6}-new \
  --uniform "$LAB"/results/range-uniform-reg-{groups,threads}-new \
  --current-source-build "$PWD/build/partial-gpu-range-rebuild-new" --out "$LAB/results/range-audit-new.json"
python3 bridge/tools/mutate_partial_gpu_range.py --same "$LAB/results/range-range-same-0-new" --separate "$LAB/results/range-range-separate-0-new" --prepare "$LAB/results/range-range-prepare-0-new"
python3 -m unittest discover -s tests
```
