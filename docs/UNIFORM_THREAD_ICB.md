# Uniform thread-grid encoding in the scoped compute ICB

The project-owned CPU ICB command now accepts `concurrentDispatchThreads:threadsPerThreadgroup:` **when every grid dimension is nonzero and exactly divisible by the corresponding nonzero local dimension**. It divides each dimension and forwards to its existing `concurrentDispatchThreadgroups:threadsPerThreadgroup:` implementation. The existing registered-pipeline, device, local-size, invocation-count, dimensional and reusable-state checks continue to apply through that implementation. Zero and partial dimensions are refused before forwarding, except for the separately opted-in [fixed partial profile](PARTIAL_ICB_FIXED_PROFILE.md); oversize, unsupported dimensional profiles and invalid reusable state still fail through the existing checks.

Apple describes the [thread-grid ICB selector](https://developer.apple.com/documentation/metal/mtlindirectcomputecommand/concurrentdispatchthreads%28_%3Athreadsperthreadgroup%3A%29?language=objc) as the indirect equivalent of `dispatchThreads`. This change implements only the aligned subset; **it does not implement partial threadgroups or general nonuniform dispatch**. It changes the scoped project ICB adapter, not the installed Apple/NVIDIA driver, device capability reporting or ordinary unmodified applications. Scope installation and a qualified native pipeline are still required. No extra system or global WindowServer integration is provided.

For example, an adapted caller can encode the same one-dimensional work either way after creating and binding a qualified command:

```objc
[command concurrentDispatchThreads:MTLSizeMake(96, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
// Equivalent within the qualified subset:
[command concurrentDispatchThreadgroups:MTLSizeMake(3, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
```

The caller normally chooses **one** of these calls. The example shows equivalence; setting the second dispatch on the same command replaces its previous dispatch state.

## Evidence on the pinned GTX 880M profile

A new seven-object archive was built from the current public source; its SHA-256 is recorded in the [cohort audit](uniform-thread-icb-validation.json). Two preparation processes, one per encoding form, built the command state and left the main user command buffer uncommitted. Preparatory native NOP/blit work can still occur during materialization; these are not zero-GPU-work processes. The pre-execution buffers were independently checked as untouched, and nine negative API cases per host were refused.

Three pairs of fresh processes then encoded the same registered `consume_grid` commands by threadgroups or by uniform threads. Across the six hosts, 42 user command buffers completed, 26,376 GPU invocations were counted, and 105,504 uint32 values matched an independent CPU oracle. Each pair had 64 byte-identical output/counter captures, including pre-execution files: 192 paired files total. The captures cover ranges, reset, CPU snapshot-copy, command reuse, local sizes 32/33/128, and one-dimensional group counts 1/3/5. There were 43,008 explicitly counted guard bytes and 72 negative API case observations including preparation hosts. These are repeated bounded tests, not 72 distinct features.

A CPU-only test invokes the actual compiled adapter method via a test subclass that records its forwarded group counts. It checks one 3D divisible conversion, a maximum-integer divided case, and nine zero/partial refusals without GPU work. This CPU test checks conversion only. A separate GPU cohort described below now covers bounded 2D/3D execution. The initial 1D GPU cohort used one pinned native function/pipeline, serial execution and one process-local scope. It does not qualify all registered shaders, native Apple ICB identity, GPU-generated ICB, concurrent execution, every Metal selector, partial groups or transparent integration. No performance comparison is claimed.

The audit reruns the raw-output CPU oracle, verifies signed hosts and frozen sources, checks identical build/profile identity and serialized process completion, and compares each pair's raw hashes. It stores source and binary fingerprints only; original system binaries and raw native GPU captures remain local. The previous refusal tests in the repository now use `33` threads with a group of `32`, so they still exercise a truly partial group instead of an aligned grid.

## Bounded 2D and 3D GPU qualification

A second, independent eight-process cohort used the **same unchanged seven-object archive** and the separately pinned `grid_coordinates` Metal library and registration manifest. Two preparation processes covered the group and thread selectors; six execution processes formed three group/thread pairs. The test includes 2D and 3D grids, a 1,024-thread local group, a local depth of 64, range selection, reshape, reset and CPU snapshot-copy. The GPU writes global, local and group coordinates, group dimensions and local dimensions; an independent CPU oracle checks every value and invocation counter.

Across 42 completed user command buffers, **111,792 GPU invocations** and **894,336 uint32 values** matched the CPU oracle. Each pair produced 180 identical data/counter files, or **540 matched files** total. Eight dimension-refusal cases per process, including a partial dimension on each axis, gave 64 expected observations across the cohort. Preparation may submit native NOP/blit work, but its main user buffer stays uncommitted.

The verifier checks 44 captured command-stream files, decodes the 38 nonempty streams, checks relocated descriptor addresses against each process's own records, and verifies QMD and built-in XYZ geometry. It does **not** require command-stream hashes to match across processes: their GPU addresses can differ. The [separate audit](uniform-icb-3d-validation.json) checks those individual streams and compares only corresponding data files. This qualifies the pinned `grid_coordinates` profile and tested serial geometry, not arbitrary 3D kernels or partial threadgroups.

To reproduce this cohort with the existing `LAB` and `RID` definitions, use the public-source archive and the previously qualified local `cpu_icb_grid3d.metallib`; its builder insists on the exact hash `5c35418c2465d1fa87396419c165ac33b5005937e8623fc40329fef30be99de0`. The associated public `bridge/src/cpu_icb_grid3d.json` is also hash-pinned. All paths must be fresh:

```sh
GRIDLIB='/path/to/qualified/cpu_icb_grid3d.metallib'
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/uniform-3d-build-new" \
  --archive build/uniform-new --metallib "$GRIDLIB"
for item in groups:prepare:01 threads:prepare:01 groups:execute:01 threads:execute:01 groups:execute:02 threads:execute:02 groups:execute:03 threads:execute:03; do
  form=${item%%:*}; rest=${item#*:}; mode=${rest%%:*}; number=${rest##*:}
  python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/uniform-3d-build-new" \
    --out "$LAB/results/uniform-3d-${form}-${mode}-${number}" --reservation-root "$LAB" \
    --form "$form" --mode "$mode" --registry-id "$RID" || break
done
python3 bridge/tools/audit_uniform_icb_3d.py \
  "$LAB/results/uniform-3d-groups-prepare-01" "$LAB/results/uniform-3d-threads-prepare-01" \
  "$LAB/results/uniform-3d-groups-execute-01" "$LAB/results/uniform-3d-threads-execute-01" \
  "$LAB/results/uniform-3d-groups-execute-02" "$LAB/results/uniform-3d-threads-execute-02" \
  "$LAB/results/uniform-3d-groups-execute-03" "$LAB/results/uniform-3d-threads-execute-03"
```

## Reproduction on the qualified machine

Build a new archive from current text sources using `python3 tools/build_from_source.py --out build/uniform-new`. Obtain the original local `indirect_compute_probe.metallib` from the existing laboratory, or compile [its source](../bridge/src/indirect_compute_probe.metal) with `xcrun metal -std=macos-metal2.0` and `xcrun metallib`. The builder requires the exact pinned hash `b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d` and fails closed if a new compiler/library differs; do not silently repin. Set `LAB` to the cooperative reservation root and `RID` to a fresh 880M registry ID. All result paths must be new.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<fresh GPU registry ID>'
METALLIB='/path/to/qualified/indirect_compute_probe.metallib'
python3 bridge/tools/uniform_thread_icb.py build \
  --out "$LAB/results/uniform-build-new" --archive build/uniform-new --metallib "$METALLIB"
for item in groups:prepare:01 threads:prepare:01 groups:execute:01 threads:execute:01 groups:execute:02 threads:execute:02 groups:execute:03 threads:execute:03; do
  form=${item%%:*}; rest=${item#*:}; mode=${rest%%:*}; number=${rest##*:}
  python3 bridge/tools/uniform_thread_icb.py run --build "$LAB/results/uniform-build-new" \
    --out "$LAB/results/uniform-${form}-${mode}-${number}" --reservation-root "$LAB" \
    --form "$form" --mode "$mode" --registry-id "$RID" || break
done
python3 bridge/tools/audit_uniform_thread_icb.py \
  "$LAB/results/uniform-groups-prepare-01" "$LAB/results/uniform-threads-prepare-01" \
  "$LAB/results/uniform-groups-execute-01" "$LAB/results/uniform-threads-execute-01" \
  "$LAB/results/uniform-groups-execute-02" "$LAB/results/uniform-threads-execute-02" \
  "$LAB/results/uniform-groups-execute-03" "$LAB/results/uniform-threads-execute-03"
KEPLER_UNIFORM_ARCHIVE="$PWD/build/uniform-new" python3 -m unittest discover -s tests -p test_uniform_thread_icb_runtime.py -v
```

A failed or incomplete host or a nonterminal GPU reservation must be inspected before any new work. A new source build has its own identity and does not inherit this cohort's results.
