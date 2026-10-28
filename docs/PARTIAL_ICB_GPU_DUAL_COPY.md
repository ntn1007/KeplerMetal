# GPU copy of a two-pipeline partial/uniform command range

The opted-in project ICB mixed-copy path has been exercised with two different certified pipelines from the same pinned registration. The first command runs `partial_builtin_barrier` from [`partial_wide_barrier.metal`](../bridge/src/partial_wide_barrier.metal) over a partial grid. It writes coordinates and geometry and uses threadgroup memory and a barrier. A uniform `partial_buffer_stencil` command then consumes those coordinates and writes a separate result. The test copies both source commands to an independently prepared destination through GPU buffer blits, resets the source and executes the destination. No runtime or system component was changed for this qualification.

A CPU oracle checks the complete input, coordinates, geometry, consumer result, counters and guard bytes. The geometry includes a witness read after the barrier. A native destination baseline writes different buffers; after the GPU copy those destination-original buffers stay unchanged and the source's producer/consumer outputs match the CPU. An additional verifier checks source and destination descriptor identities and native profile evidence for both functions (22 registers and 512 bytes of static shared memory for the producer; 11 registers and zero shared bytes for the consumer). A source/destination pair with different pipelines is refused before the copy event. Pipeline variation across slots is permitted only within the same pinned registration.

## GTX 880M evidence

Twelve new signed processes cover 96-thread 1D and 75-thread 3D cases, with preparation, native destination baselines and two executions each for same-command-buffer and separately committed same-queue ordering. The eight copied executions contain **16 logical dispatches, 1,368 shader invocations, 8,208 checked output words and 32 committed descriptor blits**. The two baselines add 342 invocations. The eight preparation-only blits are not submitted and are excluded. The 12 processes check pipeline and geometry mismatch, preparation and size refusals; all four separate-buffer executions refuse an uncommitted predecessor.

The [audit](partial-gpu-dual-copy-validation.json) re-verifies those 12 processes and six **previously captured**, nonoverlapping same-runtime controls for one-pipeline mixed copying, fully partial ranges and single-command copying. It checks frozen sources, signed executables, raw CPU oracles, native profiles, terminal GPU reservations and seven object members from a separately rebuilt runtime. [Offline mutation checks](partial-gpu-dual-copy-mutation.json) reject eight altered cases, including a changed native register profile, while the untouched evidence passes. The reservation applies to cooperating runners only; it does not reserve WindowServer or unrelated work.

This proves only the two pipelines, layouts, ordering and grid shapes tested in an adapted process. It is neither native Apple ICB support nor transparent integration into ordinary applications; cross-queue ordering, chained GPU copy, arbitrary shaders and additional grids remain unqualified. No performance gain is claimed and no system driver, framework, OCLP or firmware was modified.

## Reproduction

Obtain the pinned `DUAL` metallib and `STENCIL` inputs as in [the previous dual-pipeline qualification](PARTIAL_ICB_DUAL_PIPELINE.md), a shared reservation root `LAB`, and current GTX registry ID `RID`. Keep proprietary inputs local. Use fresh outputs; do not restart a run with a live process or unresolved reservation.

```sh
set -e
python3 tools/build_from_source.py --out build/partial-gpu-dual-copy-new
ARCHIVE="$PWD/build/partial-gpu-dual-copy-new"
python3 bridge/tools/partial_gpu_dual_copy.py build --out "$LAB/results/dual-gpu-build-new" --archive "$ARCHIVE" --metallib "$DUAL"
for n in 0 3; do
  for mode in prepare native same separate; do
    python3 bridge/tools/partial_gpu_dual_copy.py run --build "$LAB/results/dual-gpu-build-new" --out "$LAB/results/dual-gpu-$mode-$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
  done
  for mode in same separate; do
    python3 bridge/tools/partial_gpu_dual_copy.py run --build "$LAB/results/dual-gpu-build-new" --out "$LAB/results/dual-gpu-$mode-repeat-$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
  done
done
for variant in mixed_copy range copy; do
  python3 "bridge/tools/partial_gpu_${variant}.py" build --out "$LAB/results/dual-control-$variant-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
  for n in 0 3; do python3 "bridge/tools/partial_gpu_${variant}.py" run --build "$LAB/results/dual-control-$variant-build-new" --out "$LAB/results/dual-control-$variant-$n-new" --reservation-root "$LAB" --mode same --case-index "$n" --registry-id "$RID"; done
done
python3 tools/build_from_source.py --out build/partial-gpu-dual-copy-rebuild-new
python3 bridge/tools/audit_partial_gpu_dual_copy.py \
  --dual "$LAB"/results/dual-gpu-{prepare,native,same,separate,same-repeat,separate-repeat}-{0,3}-new \
  --mixed "$LAB"/results/dual-control-mixed_copy-{0,3}-new \
  --range "$LAB"/results/dual-control-range-{0,3}-new \
  --single "$LAB"/results/dual-control-copy-{0,3}-new \
  --current-source-build "$PWD/build/partial-gpu-dual-copy-rebuild-new" --out "$LAB/results/dual-gpu-audit-new.json"
python3 bridge/tools/mutate_partial_gpu_dual_copy.py --same "$LAB/results/dual-gpu-same-0-new" --separate "$LAB/results/dual-gpu-separate-0-new" --prepare "$LAB/results/dual-gpu-prepare-0-new"
python3 -m unittest discover -s tests -p 'test_partial*.py'
```
