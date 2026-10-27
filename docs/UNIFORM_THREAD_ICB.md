# Uniform thread-grid encoding in the scoped compute ICB

The project-owned CPU ICB command now accepts `concurrentDispatchThreads:threadsPerThreadgroup:` **when every grid dimension is nonzero and exactly divisible by the corresponding nonzero local dimension**. It divides each dimension and forwards to its existing `concurrentDispatchThreadgroups:threadsPerThreadgroup:` implementation. The existing registered-pipeline, device, local-size, invocation-count, dimensional and reusable-state checks continue to apply through that implementation. Zero and partial dimensions are refused before forwarding; oversize, unsupported dimensional profiles and invalid reusable state still fail through the existing checks.

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

A CPU-only test invokes the actual compiled adapter method via a test subclass that records its forwarded group counts. It checks one 3D divisible conversion, a maximum-integer divided case, and nine zero/partial refusals without GPU work. This checks conversion only; **3D GPU execution through the new selector was not run**. The GPU cohort used one pinned native function/pipeline, serial execution and one process-local scope. It does not qualify all registered shaders, native Apple ICB identity, GPU-generated ICB, concurrent execution, every Metal selector, partial groups or transparent integration. No performance comparison is claimed.

The audit reruns the raw-output CPU oracle, verifies signed hosts and frozen sources, checks identical build/profile identity and serialized process completion, and compares each pair's raw hashes. It stores source and binary fingerprints only; original system binaries and raw native GPU captures remain local. The previous refusal tests in the repository now use `33` threads with a group of `32`, so they still exercise a truly partial group instead of an aligned grid.

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
