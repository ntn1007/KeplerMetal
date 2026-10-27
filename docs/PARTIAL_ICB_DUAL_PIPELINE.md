# Bounded serial ranges with two compute pipelines

An explicitly enabled, process-local project ICB adapter accepts a serial range
containing either of two certified compute pipelines **from one registration**.
The supported profiles are a built-in/barrier producer and a buffer-stencil
consumer in one exact library and manifest. The registration, library owner,
manifest, pipeline owners and individual resource envelopes are checked; names
alone do not authorize a shader. The adapter preserves its existing bounds:
at most 1,024 grid invocations, 128 local invocations, and 16 resident launches
per range. Empty slots are skipped, and the resident transport inserts a wait
after each launch. Callers must not mutate resources until completion.

This is an adapted application's opt-in path, not an implementation of Apple's
native ICB or system-wide Metal support. It does not support arbitrary shaders,
GPU-selected commands, concurrent encoders, cross-registration mixing, or
transparent applications. Errors during preparation or encoding require the
caller to discard the uncommitted command buffer. No performance gain is
claimed. The scope and ownership restrictions in
[the previous partial-range contract](PARTIAL_ICB_CHAINED_RANGE.md) still apply.

## Qualification

The producer writes thread coordinates and a geometry/barrier witness to private
buffers; the second pipeline reads the coordinates and writes a neighbor
transform. An independent CPU oracle checks bytes and guard regions, counters,
slot/launch mappings, individual pipeline records, completion, reuse and reset.
Consumer-only and reversed-order controls verify the dependency. Short
second-slot resources and more than 16 launches are rejected before command
materialization. Four scenarios cover partial/partial, partial/uniform,
uniform/partial, and a 3D partial/partial range at exactly 16 launches.

The serialized GTX cohort includes four preparation hosts with no user shader
dispatch and eight executing hosts, two per scenario. Together the latter run
72 logical dispatches and 12,114 thread invocations, including 16 omission and
reverse-order observations. Separate old single-pipeline, barrier and uniform
regressions use the **same source-built runtime**. The machine-readable
[cohort audit](partial-dual-validation.json) checks frozen source and artifacts,
the CPU oracles, exact registration identities, process termination and
non-overlapping host intervals. This only qualifies the profiles and scenarios
listed, not every grid or Metal memory-ordering rule.

A construction-only probe captures each native pipeline before any user GPU
dispatch: the producer reports 512 bytes of static threadgroup memory and 22
registers; the consumer reports 0 bytes and 11 registers. These observations
are not by themselves execution proof. The combined locally generated library
has SHA-256 `0985a3057cd487352d801abcd180bf05a681b8dc7357ee5400db044098c32c4c`;
the source manifest has SHA-256
`c7dcdc81adba7f7ba6cf8175ecc179a086a9bd150b44d71ca1a39ad18846ef9a`.
A different compiler, SDK or native profile may produce different bytes; do not
silently change the pins. GPU tests are limited to the verified GTX 880M stack.

## Reproduction

From the repository root, choose a fresh directory under the existing lab and
reservation root `LAB`, the current GTX registry ID `RID`, and the locally
qualified standalone libraries `STENCIL`, `WIDE`, and `GRIDLIB` used by the
previous tests. Use the matching Xcode/Metal toolchain and the exact native
profile. Never overlap GPU hosts. Each `run` reserves the lab GPU and signs a
fresh immutable process. No Apple or NVIDIA binary is distributed here.

```sh
python3 tools/build_from_source.py --out build/partial-dual-new
ARCHIVE="$PWD/build/partial-dual-new"
python3 bridge/tools/partial_dual_pipeline.py build --out "$LAB/results/dual-construction-build-new"
python3 bridge/tools/partial_dual_pipeline.py run --build "$LAB/results/dual-construction-build-new" --out "$LAB/results/dual-construction-new" --reservation-root "$LAB" --registry-id "$RID"
DUAL="$LAB/results/dual-construction-new/assets/shader.metallib"
python3 bridge/tools/partial_dual_chain.py build --out "$LAB/results/dual-build-new" --archive "$ARCHIVE" --metallib "$DUAL"
for n in 0 1 2 3; do
  python3 bridge/tools/partial_dual_chain.py run --build "$LAB/results/dual-build-new" --out "$LAB/results/dual-prepare-$n-new" --reservation-root "$LAB" --mode prepare --case-index "$n" --registry-id "$RID" || break
  python3 bridge/tools/partial_dual_chain.py run --build "$LAB/results/dual-build-new" --out "$LAB/results/dual-case-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
  python3 bridge/tools/partial_dual_chain.py run --build "$LAB/results/dual-build-new" --out "$LAB/results/dual-repeat-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/partial_range_chain.py build --out "$LAB/results/dual-old-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do
  python3 bridge/tools/partial_range_chain.py run --build "$LAB/results/dual-old-build-new" --out "$LAB/results/dual-old-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/partial_chain_barrier.py build --out "$LAB/results/dual-barrier-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
for n in 0 6; do
  python3 bridge/tools/partial_chain_barrier.py run --build "$LAB/results/dual-barrier-build-new" --out "$LAB/results/dual-barrier-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/dual-uniform-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
for form in groups threads; do
  python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/dual-uniform-build-new" --out "$LAB/results/dual-uniform-$form-new" --reservation-root "$LAB" --mode execute --form "$form" --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_dual_chain.py \
  --dual "$LAB/results/dual-prepare-0-new" "$LAB/results/dual-prepare-1-new" "$LAB/results/dual-prepare-2-new" "$LAB/results/dual-prepare-3-new" "$LAB/results/dual-case-0-new" "$LAB/results/dual-case-1-new" "$LAB/results/dual-case-2-new" "$LAB/results/dual-case-3-new" "$LAB/results/dual-repeat-0-new" "$LAB/results/dual-repeat-1-new" "$LAB/results/dual-repeat-2-new" "$LAB/results/dual-repeat-3-new" \
  --chain "$LAB/results/dual-old-0-new" "$LAB/results/dual-old-3-new" \
  --barrier "$LAB/results/dual-barrier-0-new" "$LAB/results/dual-barrier-6-new" \
  --uniform "$LAB/results/dual-uniform-groups-new" "$LAB/results/dual-uniform-threads-new" --current-source-build "$ARCHIVE"
python3 -m unittest discover -s tests -p test_partial_dual_chain_oracle.py -v
```

Preparation can issue bounded initialization/blit work, but does not commit the
recorded user shader commands. A stopped, failed or inconclusive host must be
resolved to a terminal reservation state before another GPU experiment.
