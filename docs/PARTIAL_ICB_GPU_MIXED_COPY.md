# GPU copy of mixed partial and uniform command ranges

This page records the earlier single-shader qualification. The later [two-pipeline test](PARTIAL_ICB_GPU_DUAL_COPY.md) extends its evidence.

The process-local project ICB adapter can copy a prepared range containing both partial and uniform commands. Both `enableExperimentalPartialGridWithError:` and `enableExperimentalPartialGPUCopyWithError:` are required. Prepare each partial command with `prepareExperimentalPartialGPUCopyCommand:index:error:` and each uniform command with `prepareResidentComputeCommands:range:error:` before recording the copy. The entire range is validated before any copy or shadow-state change. Every pair must have the same certified pipeline, kind and geometry, the same registration, valid resource windows that do not alias within each command, and initialized disjoint descriptor allocations. The range is limited to eight physical QMDs and sixteen retained owners.

The adapter encodes one native Metal buffer blit per physical QMD and retains both endpoint records and resources. A copied uniform command is explicitly distinguished from a GPU-selected command: CPU snapshot overwrites and pipeline, binding and dispatch setters require reset, chained copying is refused, and execution checks its ordering and retained owners. A consumer is qualified in the same recording command buffer or in a later not-yet-enqueued retained buffer after its predecessor is committed on the same queue. CPU mutation and contents of user resources still require caller synchronization. If encoding fails, discard the uncommitted buffer. This is an opt-in project ICB, not native Apple ICB support or transparent system integration.

## GTX 880M qualification

Two 12-process cohorts test dependent producer/consumer commands in both orders: partial then uniform, and uniform then partial. Each uses 96-thread 1D and 75-thread 3D grids, with a preparation-only case, a destination baseline and two repeated executions for each of the same-buffer and separately committed same-queue modes. The 16 copied executions submit **64 descriptor blits**, execute **2,736 logical shader invocations**, and yield **10,944 exact 32-bit output values** checked by CPU oracles. The four destination baselines add 684 invocations; preparation-only blits were not submitted and are excluded. Oracles also check inputs, counters and guard bytes. Separate-buffer tests refuse an uncommitted predecessor, and all test unprepared and mismatched uniform commands and the existing partial-range controls.

Two additional preparation-only hosts check that mixed ranges exceeding eight descriptors are refused before encoding. Six more hosts retest fully partial range copies, mixed execution after a partial copy, and the earlier single-copy path with the same runtime. The [audit](partial-gpu-mixed-copy-validation.json) independently rechecks frozen source and tool hashes, signed host identities, outputs, terminal reservations, nonoverlapping intervals and the seven object members of a separate rebuild. The [offline mutation checks](partial-gpu-mixed-copy-mutation.json) confirm that altered outputs, guards, descriptors, ordering, refusal evidence and reservation state are rejected. The full CPU suite passes 500 tests with one skipped. The common reservation coordinates participating runners only, not unrelated GPU processes or WindowServer.

These cohorts test one registered shader and selected geometry. The adapter also permits one other exact registered shader, which was not retested for this mixed-copy extension. These results do not prove the full Metal ICB contract. Chained GPU copies, GPU-selected source commands, cross-queue ordering and arbitrary shaders remain unqualified. No performance claim is made and no driver, system framework, OCLP or firmware was changed.

## Reproduction

Use `LAB`, `RID`, and the pinned `STENCIL` described in [the previous range qualification](PARTIAL_ICB_GPU_RANGE.md). Use fresh paths. The build and runs below use one runtime; do not repeat a run while its signed process or reservation is unresolved. Binary inputs and captures remain local.

```sh
set -e
python3 tools/build_from_source.py --out build/partial-gpu-mixed-copy-new
ARCHIVE="$PWD/build/partial-gpu-mixed-copy-new"
for variant in mixed_copy mixed_reverse; do
  python3 "bridge/tools/partial_gpu_${variant}.py" build --out "$LAB/results/$variant-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
  for n in 0 3; do
    for mode in prepare native same separate; do
      python3 "bridge/tools/partial_gpu_${variant}.py" run --build "$LAB/results/$variant-build-new" --out "$LAB/results/$variant-$mode-$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
    done
    for mode in same separate; do
      python3 "bridge/tools/partial_gpu_${variant}.py" run --build "$LAB/results/$variant-build-new" --out "$LAB/results/$variant-$mode-repeat-$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
    done
  done
done
python3 bridge/tools/partial_gpu_mixed_limit.py build --out "$LAB/results/mixed-limit-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do python3 bridge/tools/partial_gpu_mixed_limit.py run --build "$LAB/results/mixed-limit-build-new" --out "$LAB/results/mixed-limit-$n-new" --reservation-root "$LAB" --mode prepare --case-index "$n" --registry-id "$RID"; done
for variant in range uniform copy; do
  python3 "bridge/tools/partial_gpu_${variant}.py" build --out "$LAB/results/mixed-reg-$variant-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
  for n in 0 3; do
    python3 "bridge/tools/partial_gpu_${variant}.py" run --build "$LAB/results/mixed-reg-$variant-build-new" --out "$LAB/results/mixed-reg-$variant-$n-new" --reservation-root "$LAB" --mode same --case-index "$n" --registry-id "$RID"
  done
done
python3 tools/build_from_source.py --out build/partial-gpu-mixed-copy-rebuild-new
python3 bridge/tools/audit_partial_gpu_mixed_copy.py \
  --mixed-copy "$LAB"/results/mixed_copy-{prepare,native,same,separate,same-repeat,separate-repeat}-{0,3}-new \
  --reverse "$LAB"/results/mixed_reverse-{prepare,native,same,separate,same-repeat,separate-repeat}-{0,3}-new \
  --limit "$LAB"/results/mixed-limit-{0,3}-new \
  --range "$LAB"/results/mixed-reg-range-{0,3}-new \
  --uniform "$LAB"/results/mixed-reg-uniform-{0,3}-new \
  --single "$LAB"/results/mixed-reg-copy-{0,3}-new \
  --current-source-build "$PWD/build/partial-gpu-mixed-copy-rebuild-new" --out "$LAB/results/mixed-copy-audit-new.json"
python3 bridge/tools/mutate_partial_gpu_mixed_copy.py --same "$LAB/results/mixed_copy-same-0-new" --separate "$LAB/results/mixed_copy-separate-0-new" --prepare "$LAB/results/mixed_copy-prepare-0-new"
python3 -m unittest discover -s tests
```
