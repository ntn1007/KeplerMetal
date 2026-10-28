# Overlapping CPU snapshots of partial ICB commands

The existing opt-in CPU snapshot operation is now qualified for overlapping source and destination ranges **within the same project ICB**, in both directions. It first snapshots all source slots before assigning destination slots. The tested range contains two certified partial-grid commands and an empty slot; the copy retains the commands' bindings and rematerializes their partial native records. The source-only slot outside the destination range is reset before execution.

This is a qualification of the existing CPU snapshot implementation, not a change to the runtime and not the GPU-timeline Metal `copyIndirectCommandBuffer` operation. The latter still refuses these decomposed partial commands. Both explicit opt-ins, the exact registered shader, scope, resource and geometry limits from [the snapshot contract](PARTIAL_ICB_SNAPSHOT.md) remain required. Applications must synchronize CPU mutation and preserve resources through completion. Other overlap shapes, arbitrary shaders and native Apple ICB identity remain unqualified.

## GTX evidence

Six fresh signed, nonoverlapping hosts cover preparation and two executions per direction. The forward copy moves slots 0–2 to 1–3 using the 1D case; the backward copy moves slots 1–3 to 0–2 using the 3D case with 16 physical launches. The previously materialized source records are not reused as the copied partial records. Together the execution hosts check **36 logical dispatches, 8,658 invocations and 34,632 output words**, including the omission and reversed-order controls. Source data, counters, guards, cache reuse and reset are checked by the CPU oracle. Before opting in, the same partial copy is refused; an out-of-bounds range is also refused.

The independent [audit](partial-overlap-validation.json) rechecks all receipts, signatures, runtime and source hashes, and each frozen oracle. It compares 240 complete raw output files byte-for-byte with the preceding nonoverlapping snapshot cases on the same runtime archive. These earlier files are references, not additional new GPU runs. The two directions use different geometries; this cohort does not isolate geometry from direction or establish every possible overlap. No performance result or system modification is claimed.

## Reproduction

Use the pinned locally generated `STENCIL`, existing laboratory reservation root `LAB`, current GTX registry ID `RID`, and a current source-built runtime `ARCHIVE` as in [the earlier qualification](PARTIAL_ICB_SNAPSHOT.md). Use fresh paths and stop if a process or lease is unresolved. The audit requires the earlier nonoverlapping reference runs as `REF0` and `REF3`.

```sh
set -e
python3 bridge/tools/partial_overlap.py build --out "$LAB/results/overlap-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do
  for kind in prepare execute repeat; do
    mode=execute; [ "$kind" = prepare ] && mode=prepare
    python3 bridge/tools/partial_overlap.py run --build "$LAB/results/overlap-build-new" \
      --out "$LAB/results/overlap-$kind$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
  done
done
python3 bridge/tools/audit_partial_overlap.py --overlap \
  "$LAB/results/overlap-prepare0-new" "$LAB/results/overlap-execute0-new" "$LAB/results/overlap-repeat0-new" \
  "$LAB/results/overlap-prepare3-new" "$LAB/results/overlap-execute3-new" "$LAB/results/overlap-repeat3-new" \
  --reference "$REF0" "$REF3" --out "$LAB/results/overlap-audit-new.json"
python3 -m unittest discover -s tests -p 'test_partial*.py' -v
```

The cooperative GPU reservation does not exclude unrelated workloads. Proprietary libraries and raw captures remain in the laboratory and are not published.
