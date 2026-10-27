# Bounded partial-grid resources with variable sizes and offsets

The opt-in project ICB partial-grid adapter now accepts appropriately sized and
aligned resource windows for the two already certified shaders. Previously it
required one exact length and offset for each binding. These are still
process-local adapted-application commands, not native Apple ICB support or a
system-driver change.

For a grid of `N` logical invocations, bindings 0 and 1 must each provide
`16*N` bytes from their 16-byte-aligned offsets; binding 2 needs four bytes at a
four-byte-aligned offset; and binding 3 needs at least 512 bytes at a
256-byte-aligned offset, with no more than 65,536 bytes remaining. The first
three buffers remain Private and the last Shared. All four whole GPU allocation
ranges must be valid, distinct and disjoint. The check uses the complete logical
grid, not just the largest physical region. Existing shader and manifest
fingerprints, geometry limits, serial execution and resource lifetimes still
apply. Callers must preserve input and parameter contents through completion.

This check does not guarantee that every aligned constant-buffer window can be
used. The native driver can round its encoded constant-bank size; the existing
transport validates the actual address and size against the retained buffer
and refuses a mismatch before user dispatch. An initial test process aborted
while releasing an unended encoder and did not produce a complete result; the
test host was corrected. Two subsequent trials with a 256-byte parameter
offset reported refusal before a user command buffer was submitted: native
sizes were 768 versus 512 and 1,280 versus 1,024 bytes remaining. All three
processes were observed terminal. Eight
subsequent native construction-only captures showed sizes and addresses for
different parameter windows, without committing or dispatching commands. This
observation is bounded to the tested profile; it does not establish a general
hardware rounding rule.

## GTX qualification

The new runtime archive was built from the published source. Ten fresh
execution hosts covered eight stencil geometries plus two repetitions, with
**13,712 invocations** and 54,848 CPU-checked output words. Five barrier-shader
hosts covered four geometries plus one repetition, with **7,940 invocations**
and 63,520 checked output words. Both exercised data offsets 128/512, counter
offsets 32/128 and parameter offsets 256/512. Input or output allocations
were sized to the logical grid plus their offset and a 64-byte trailing guard;
the parameter buffers used windows whose captured native sizes matched.

Two additional barrier hosts using the former fixed envelope produced 5,632
correct invocations. Two uniform-grid hosts produced 37,264 correct invocations.
Together with two no-user-dispatch preparation hosts, the 21 processes used the
same runtime archive. The [independent audit](partial-variable-validation.json)
rechecked raw CPU oracles, guard bytes, source and executable fingerprints,
terminal reservations, and nonoverlapping cohort process intervals. There
were 217 recorded partial-path negative-control observations, including
repetitions and preparation; they are not 217 different failure modes.
The audit does not qualify every accepted grid, offset, synchronization pattern
or shader, and it is not a performance benchmark.

## Reproduction

The required metallib and laboratory reservation root are locally generated
or retained; proprietary binaries are not distributed. Select the current GPU
registry ID as `RID` and use new output paths throughout:

```sh
python3 tools/build_from_source.py --out build/partial-variable-new
ARCHIVE="$PWD/build/partial-variable-new"
python3 bridge/tools/partial_variable_resources.py build --out "$LAB/results/variable-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
python3 bridge/tools/partial_variable_resources.py run --build "$LAB/results/variable-build-new" --out "$LAB/results/variable-prepare-new" --reservation-root "$LAB" --mode prepare --case-index 0 --registry-id "$RID"
for n in 0 1 2 3 4 5 6 7; do
  python3 bridge/tools/partial_variable_resources.py run --build "$LAB/results/variable-build-new" --out "$LAB/results/variable-case-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/partial_variable_barrier.py build --out "$LAB/results/variable-barrier-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
python3 bridge/tools/partial_variable_barrier.py run --build "$LAB/results/variable-barrier-build-new" --out "$LAB/results/variable-barrier-prepare-new" --reservation-root "$LAB" --mode prepare --case-index 0 --registry-id "$RID"
for n in 0 1 6 7; do
  python3 bridge/tools/partial_variable_barrier.py run --build "$LAB/results/variable-barrier-build-new" --out "$LAB/results/variable-barrier-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
for n in 1 6; do
  python3 bridge/tools/partial_variable_resources.py run --build "$LAB/results/variable-build-new" --out "$LAB/results/variable-case-$n-repeat-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/partial_variable_barrier.py run --build "$LAB/results/variable-barrier-build-new" --out "$LAB/results/variable-barrier-0-repeat-new" --reservation-root "$LAB" --mode execute --case-index 0 --registry-id "$RID"
python3 bridge/tools/partial_general_api.py build --out "$LAB/results/variable-fixed-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
for n in 0 6; do
  python3 bridge/tools/partial_general_api.py run --build "$LAB/results/variable-fixed-build-new" --out "$LAB/results/variable-fixed-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/variable-uniform-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
for form in groups threads; do
  python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/variable-uniform-build-new" --out "$LAB/results/variable-uniform-$form-new" --reservation-root "$LAB" --mode execute --form "$form" --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_variable_resources.py \
  --stencil "$LAB/results/variable-prepare-new" "$LAB/results/variable-case-0-new" "$LAB/results/variable-case-1-new" "$LAB/results/variable-case-2-new" "$LAB/results/variable-case-3-new" "$LAB/results/variable-case-4-new" "$LAB/results/variable-case-5-new" "$LAB/results/variable-case-6-new" "$LAB/results/variable-case-7-new" "$LAB/results/variable-case-1-repeat-new" "$LAB/results/variable-case-6-repeat-new" \
  --barrier "$LAB/results/variable-barrier-prepare-new" "$LAB/results/variable-barrier-0-new" "$LAB/results/variable-barrier-1-new" "$LAB/results/variable-barrier-6-new" "$LAB/results/variable-barrier-7-new" "$LAB/results/variable-barrier-0-repeat-new" \
  --fixed "$LAB/results/variable-fixed-0-new" "$LAB/results/variable-fixed-6-new" \
  --uniform "$LAB/results/variable-uniform-groups-new" "$LAB/results/variable-uniform-threads-new"
python3 -m unittest discover -s tests -p test_partial_grid_plan_cpp.py -v
python3 -m unittest discover -s tests -p 'test_partial*oracle.py' -v
```

`WIDE` is the separately qualified barrier metallib and `GRIDLIB` the uniform-grid metallib. Each run uses a fresh signed process and the common host reservation, then
compares every saved output and guard byte with its CPU oracle. The extra
controls check aliasing, alignment, minimum/maximum parameter lengths, and a
buffer large enough for an individual region but too small for the full grid.
See [the previous shader qualification](PARTIAL_ICB_BUFFER_STENCIL.md) for the
original fixed-envelope evidence and its limitations.
