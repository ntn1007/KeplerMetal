# A second bounded partial-grid shader

The opt-in, process-local project ICB adapter accepts a second exact shader and manifest pair: [`partial_buffer_stencil`](../bridge/src/partial_buffer_stencil.metal) and its [reflected manifest](../bridge/src/partial_buffer_stencil.json). It reads an immutable `uint4` input array and writes a separate output array, applying a deterministic transform involving the next input element, wrapping at the end of the grid. A separate atomic counter records invocations. This tests useful inter-element buffer reads and writes beyond the previous built-in/barrier diagnostic. The `partial_builtin_barrier` pair remains available.

The pipeline, library **and manifest hashes**, registration ownership and profile must match one of the two exact pairs; arbitrary shaders remain refused. Existing grid limits, serial execution, disjoint resource ranges, device and lifetime checks remain in force. [Variable resource sizes and offsets](PARTIAL_ICB_VARIABLE_RESOURCES.md) were added after this original fixed-envelope cohort. The client must preserve the input and other resources until completion; the implementation is a project-owned adapter for explicitly adapted applications, not an Apple ICB implementation or a transparent system-driver update.

## Evidence and limitations

On the GTX 880M, a signed, construction-only probe reflected all four buffer arguments and recorded 11 native registers and zero static shared memory; it did not submit the shader. Using the same compiled library and profile, 12 fresh signed execution hosts tested eight 1D/2D/3D grids, including repeated processes for a 385-invocation 3D grid and a 1,023-invocation 1D grid. Four command buffers per host exercised initial materialization, reuse, rebinding and reset, with scope restoration before the final commit. The resulting **20,120 shader invocations and 80,480 output uint32 values** match an independent CPU oracle. Input bytes remain unchanged, output and counter guards are checked, and 104 recorded negative refusals cover disabled opt-in, wrong bounds, alias, short buffer, mixed range, copying and resident export. These counts include repeated observations, not 104 distinct failure types.

The input contained 1,024 deterministic `uint4` elements; the parameter values were `count = 1024` and `seed = 0x3141` in this cohort. Other input values and parameter values are not separately qualified by these tests. The shader is not a general implementation for arbitrary computations. Tests cover bounded cases, not all accepted grids, memory models or synchronization patterns. No performance benchmark or improvement is claimed.

Two same-runtime previous-shader regression hosts matched their CPU oracle for **5,632 invocations**. Two separate uniform-grid regression hosts matched **37,264 invocations and 298,112 uint32 values**, with 180 paired data files identical between group and thread dispatch forms. The [auditor](../bridge/tools/audit_partial_stencil_api.py) rechecks signed immutable hosts, serialized GPU reservations, command-stream metadata, frozen artifacts, CPU outputs and guards; the sanitized [audit result](partial-stencil-validation.json) contains hashes and counts, not proprietary binaries.

## Reproduction on the qualified machine

The builders refuse changes to pinned shader, OS driver profile, SDK or source. `LAB` must point to the existing laboratory and shared reservation root, `RID` to the current GTX registry ID, and `GRIDLIB` to the already qualified uniform-grid library. Every destination must be new. Exact library bytes depend on the toolchain: an output with a different hash must be separately investigated and qualified, never silently repinned.

```sh
python3 tools/build_from_source.py --out build/partial-stencil-new
ARCHIVE="$PWD/build/partial-stencil-new"
python3 bridge/tools/partial_stencil_pipeline.py build --out "$LAB/results/stencil-pipeline-build-new"
python3 bridge/tools/partial_stencil_pipeline.py run --build "$LAB/results/stencil-pipeline-build-new" --out "$LAB/results/stencil-pipeline-new" --reservation-root "$LAB" --registry-id "$RID"
STENCIL="$LAB/results/stencil-pipeline-new/assets/shader.metallib"
python3 bridge/tools/partial_stencil_api.py build --out "$LAB/results/stencil-api-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
python3 bridge/tools/partial_stencil_api.py run --build "$LAB/results/stencil-api-build-new" --out "$LAB/results/stencil-prepare-new" --reservation-root "$LAB" --mode prepare --case-index 0 --registry-id "$RID"
for n in 0 1 2 3 4 5 6 7; do
  python3 bridge/tools/partial_stencil_api.py run --build "$LAB/results/stencil-api-build-new" --out "$LAB/results/stencil-case-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
for n in 0 6; do
  for rep in 2 3; do
    python3 bridge/tools/partial_stencil_api.py run --build "$LAB/results/stencil-api-build-new" --out "$LAB/results/stencil-case-$n-repeat-$rep-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break 2
  done
done
python3 bridge/tools/partial_general_api.py build --out "$LAB/results/stencil-old-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
for n in 0 6; do
  python3 bridge/tools/partial_general_api.py run --build "$LAB/results/stencil-old-build-new" --out "$LAB/results/stencil-old-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/stencil-uniform-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
for form in groups threads; do
  python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/stencil-uniform-build-new" --out "$LAB/results/stencil-uniform-$form-new" --reservation-root "$LAB" --mode execute --form "$form" --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_stencil_api.py \
  "$LAB/results/stencil-pipeline-new" "$LAB/results/stencil-prepare-new" \
  "$LAB/results/stencil-case-0-new" "$LAB/results/stencil-case-1-new" "$LAB/results/stencil-case-2-new" "$LAB/results/stencil-case-3-new" \
  "$LAB/results/stencil-case-4-new" "$LAB/results/stencil-case-5-new" "$LAB/results/stencil-case-6-new" "$LAB/results/stencil-case-7-new" \
  "$LAB/results/stencil-case-0-repeat-2-new" "$LAB/results/stencil-case-0-repeat-3-new" "$LAB/results/stencil-case-6-repeat-2-new" "$LAB/results/stencil-case-6-repeat-3-new" \
  "$LAB/results/stencil-old-0-new" "$LAB/results/stencil-old-6-new" "$LAB/results/stencil-uniform-groups-new" "$LAB/results/stencil-uniform-threads-new"
```

`WIDE` is the original pinned barrier-shader library from the earlier bounded-grid qualification. Run the final auditor only after every cohort reports PASS; it refuses missing or changed evidence. These tests must not overlap other GPU work, and the reservation must be terminal before another signed host starts.
