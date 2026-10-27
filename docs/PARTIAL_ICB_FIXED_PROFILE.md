# Historical fixed-profile partial dispatch qualification

The current adapter supports additional bounded geometries as described in [the newer contract](PARTIAL_ICB_BOUNDED_PROFILE.md). The remaining text records the earlier exact-grid qualification and its then-current limits.

Later changes also support [variable resource windows](PARTIAL_ICB_VARIABLE_RESOURCES.md) and [bounded serial ranges](PARTIAL_ICB_CHAINED_RANGE.md); the historical refusals below remain part of the earlier evidence.

The process-local CPU ICB adapter has an **explicitly enabled, exact-profile** path for `concurrentDispatchThreads:threadsPerThreadgroup:`. It accepts one grid, **11 × 7 × 5 threads with nominal groups 4 × 4 × 3**, for the exact registered `partial_builtin_barrier` shader and manifest. This is an experimental adapted-application feature, not support for arbitrary partial grids or shaders, Apple's native ICB ABI, an installed driver, or transparent use by ordinary applications. Capabilities advertised by `MTLDevice` are unchanged. The ordinary aligned-grid path remains available without this opt-in; unsupported partial grids continue to be refused.

The caller registers the verified [wide shader manifest](../bridge/src/partial_wide_barrier.json) through the existing scope installation, then opts in before encoding the command:

```objc
NSError *error = nil;
if (![scope enableExperimentalPartialGridWithError:&error]) {
    // Handle the refusal; do not encode the unsupported command.
}
id<MTLIndirectComputeCommand> command = [projectICB indirectComputeCommandAtIndex:0];
[command setComputePipelineState:[scope pipelineForFunction:@"partial_builtin_barrier"]];
// Bind the four qualified resources described below.
[command concurrentDispatchThreads:MTLSizeMake(11, 7, 5)
             threadsPerThreadgroup:MTLSizeMake(4, 4, 3)];
// Adapt a serial compute encoder from the same queue and execute this one slot.
```

The selected range must contain exactly this one command. The encoder must be serial, in an uncommitted command buffer with retained references from the scope's queue. Resource indices 0 and 1 must each be a distinct 16,512-byte Private buffer bound at offset 64; index 2 must be a distinct 132-byte Private counter bound at offset 64; index 3 must be a distinct 1,536-byte Shared parameter buffer bound at offset 256. All belong to the scope device. The shader's output and counter layout and the parameter structure are defined in the linked MSL source. Pipeline registration, library SHA-256, manifest SHA-256 and reflected ABI must match exactly. CPU snapshot copies, GPU-selected commands, mixed command ranges and other resource envelopes are refused before partial execution. Callers must externally synchronize concurrent mutation and preserve resource contents through command-buffer completion.

Internally, the adapter materializes eight already checked native records, initializes their private QMDs and built-in data, then encodes eight serialized resident launches. Preparation may submit and wait for native NOP and blit work, but does not launch the user shader. Records are retained until completion; rebinding or resetting invalidates their cache. The adapter restores its process-local scope as before. No GPU command packets or system driver are newly invented or installed by this feature. This serialization can change cross-group scheduling compared with a single native dispatch; the certified shader has no cross-group dependency. Do not extrapolate this result to shaders with such dependencies.

## Qualification

A fresh seven-object archive was built from the updated public sources. One preparation host and three fresh execution hosts ran under the shared GTX reservation. Each host checks seven explicit negative cases, including disabled opt-in, unsupported grid/local size, copy, mixed range, aliased buffers and a too-small buffer; their actual refusal reasons are checked. Preparation verifies the outputs before submission. Each execution host checks four full partial-grid command buffers: initial materialization, cached reuse, rebind invalidation, and reset/re-encoding with scope restoration before commit. Across those hosts, **12 command buffers, 4,620 GPU invocations and 36,960 uint32 output values** match the independent CPU oracle; the pre-commit and no-dispatch outputs remain untouched. The audit rechecks the resident launch stream, exact profile, signatures, process termination, source and archive hashes, full output buffers and guards. There are **28 refusal observations**, not 28 distinct cases.

All 24 coordinate/geometry files for the 12 positive executions match the independently qualified manual 3D prototype. Across the two prior M1 Max reference captures, **194,040 metadata components** match the GTX results. The M1 data is a previously captured reference, not a new execution or proof of GTX execution; barrier witnesses are separately checked against CPU oracles.

The same new archive also passed two fresh GTX regression hosts for ordinary uniform 2D/3D group and thread selectors: **37,264 invocations and 298,112 uint32 values**, with 180 paired output files identical between forms. These regressions include a 1,024-thread local group and depth 64. They do not qualify every existing project path or all partial grids. The [audit](partial-icb-api-validation.json) includes exact host, runtime, driver-file, reference and process-manifest hashes; raw GPU captures and proprietary material remain in the local lab.

## Reproduce

These historical commands require the source checkout at commit `42818ddd7fc341f917433522cca8fd6495ebd556`; later versions broaden the adapter and change its events. The builder requires macOS/Xcode and the exact source/profile pins. Set a common `LAB` reservation root, the currently observed GTX `RID`, a fresh source-only archive `ARCHIVE`, the pinned wide shader `WIDE`, an existing manual prototype capture `PROTO`, and the two-cohort M1 reference directory `M1_ROOT`. Use fresh paths and execute serially:

```sh
python3 tools/build_from_source.py --out build/partial-icb-new
ARCHIVE="$PWD/build/partial-icb-new"
python3 bridge/tools/partial_icb_api.py build --out "$LAB/results/partial-icb-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
python3 bridge/tools/partial_icb_api.py run --build "$LAB/results/partial-icb-build-new" --out "$LAB/results/partial-icb-prepare-new" --reservation-root "$LAB" --mode prepare --registry-id "$RID"
for run in 1 2 3; do
  python3 bridge/tools/partial_icb_api.py run --build "$LAB/results/partial-icb-build-new" --out "$LAB/results/partial-icb-execute-new-$run" --reservation-root "$LAB" --mode execute --registry-id "$RID" || break
done
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/partial-uniform-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
for form in groups threads; do
  python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/partial-uniform-build-new" --out "$LAB/results/partial-uniform-$form-new" --reservation-root "$LAB" --mode execute --form "$form" --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_icb_api.py "$LAB/results/partial-icb-prepare-new" "$LAB/results/partial-icb-execute-new-1" "$LAB/results/partial-icb-execute-new-2" "$LAB/results/partial-icb-execute-new-3" "$LAB/results/partial-uniform-groups-new" "$LAB/results/partial-uniform-threads-new" "$PROTO" "$M1_ROOT"
```

A changed shader/compiler, device or driver profile requires independent qualification; the builders refuse mismatches rather than repinning. No performance improvement is claimed.
