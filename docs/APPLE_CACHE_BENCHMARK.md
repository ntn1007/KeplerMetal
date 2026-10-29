# Paired CPU measurement of the inherited-record cache

This measures the [scoped Apple render-record cache](APPLE_INHERITED_CACHE.md)
on the GTX 880M using the instrumented Apple storyboard/controller and the
same alternating eight-frame workload. It times only the application's call to
`executeCommandsInBuffer:withRange:`. Wall time uses `CLOCK_MONOTONIC` and the
calling thread's CPU time uses `CLOCK_THREAD_CPUTIME_ID`. It does **not** measure
GPU execution time, full-frame time, window presentation, frame rate or system
CPU usage. Event collection, state validation and timing calls are enabled in
both versions.

The baseline archive was built from `be5db8cb9671e9117d38536ed3450e8d1ad5020f`;
the cache archive was built from `9da8cefbe77109f1ec181a2c94b646a959923182`.
Both use x86_64, SDK 26.2 and Apple clang 17.0.0 (1700.6.4.2). The auditor
checks that their source and object manifests differ only for
`KeplerCPUICB.mm`/`.o`, that client and test assets match, and that all runs
load the **same compiled storyboard**. Both explicitly opt into the prototype.
This compares two versions of our adapter, not two installed NVIDIA drivers.

Six serial process pairs alternate which version runs first. Each process draws
eight frames; frame 0 warms the profile, frame 4 deliberately changes a mesh
binding and exercises its refusal control. Frames 1–3 and 5–7 are the six
retained cache-hit observations per process. For each process we take the
median of those six values, then report the median of the six process medians.
The paired ratio is the median of each pair's baseline/cache process-median
ratio; it is not the ratio of the two displayed medians.

| Measured scope | Baseline median | Cache median | Median paired ratio |
| --- | ---: | ---: | ---: |
| Calling-thread CPU | 5.257 ms | 1.914 ms | 2.747× |
| Wall time | 5.272 ms | 1.917 ms | 2.748× |

For this workload, the ratio of displayed CPU medians corresponds to a 63.6%
reduction. This small, single-machine sample is not a general performance
claim; no confidence interval or application-level improvement is established.
The alternating order reduces but does not eliminate drift, contention or
thermal effects. The timed code includes project event recording, so these
numbers characterize this instrumented build. The two initial exploratory
series used separately compiled storyboards; they are archived locally and
excluded from these statistics.

The [independent auditor](apple-cache-benchmark-validation.json) checks all
14 signed terminal processes: 12 benchmark and two direct/blank controls,
112 frames, 344,064 pixels, 57,344 guard bytes and 1,440 adapted draw packets.
All benchmark images match the direct control; blank images differ. Every
baseline process materializes 120 records; every cache process materializes 16
and reuses 104. Each has eight invalid depth-store refusals and one invalid
vertex-binding refusal before user command-buffer commit. The private frame
buffer receives the sample's per-frame blit. A bounded set of 83 system-file
hashes remained unchanged. The source and object comparisons do not prove
behavior for other shaders, machines, workloads or OS versions.

## Reproduce

Use the matching x86_64 toolchain and pinned Apple source, local metallib and
legacy carrier from [APPLE_CPU_ICB_GAP.md](APPLE_CPU_ICB_GAP.md). This example
creates a temporary source snapshot of the baseline commit under the existing
build directory; it does not modify the current checkout. Use fresh directories.
The test briefly displays a window, runs serially under the shared GPU
reservation, and stores private compiled resources only in the laboratory.

```sh
ROOT="$PWD"
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
mkdir build/cache-bench-baseline-source-new
git archive be5db8cb9671e9117d38536ed3450e8d1ad5020f | tar -x -C build/cache-bench-baseline-source-new
(cd build/cache-bench-baseline-source-new && python3 tools/build_from_source.py --out "$ROOT/build/cache-bench-baseline-new")
python3 tools/build_from_source.py --out build/cache-bench-current-new
OLD="$ROOT/build/cache-bench-baseline-new"
NEW="$ROOT/build/cache-bench-current-new"
E=bridge/experiments/apple_cache_benchmark
B0="$LAB/results/cache-bench-baseline-build-new"
B1="$LAB/results/cache-bench-current-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$OLD" --sample "$S" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B0"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$NEW" --sample "$S" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B1"
for n in 01 02 03 04 05 06; do
  if (( 10#$n % 2 == 0 )); then order=(cache baseline); else order=(baseline cache); fi
  for version in "${order[@]}"; do
    if [[ "$version" == baseline ]]; then b="$B0"; else b="$B1"; fi
    python3 "$E/experiment.py" run --lab "$LAB" --build "$b" --storyboard-build "$B1" --mode auto --out "$LAB/results/cache-bench-$version-$n-new"
  done
done
for mode in direct blank; do
  python3 "$E/experiment.py" run --lab "$LAB" --build "$B1" --storyboard-build "$B1" --mode "$mode" --out "$LAB/results/cache-bench-control-$mode-new"
done
runs=()
for n in 01 02 03 04 05 06; do
  runs+=("$LAB/results/cache-bench-baseline-$n-new" "$LAB/results/cache-bench-cache-$n-new")
done
python3 "$E/audit.py" --sample "$S" --baseline-build "$B0" --cache-build "$B1" --baseline-archive "$OLD" --cache-archive "$NEW" --direct "$LAB/results/cache-bench-control-direct-new" --blank "$LAB/results/cache-bench-control-blank-new" --runs "${runs[@]}" --out "$LAB/results/cache-bench-audit-new.json"
```
