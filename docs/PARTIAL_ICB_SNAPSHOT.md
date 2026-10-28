# CPU snapshots of certified partial-grid commands

The process-local project ICB adapter can now copy CPU-encoded partial-grid command state through `KPCopyCPUICBCommands` after two explicit opt-ins: the existing partial-grid switch and the new `enableExperimentalPartialSnapshotCopyWithError:`. The default remains a refusal. The copied command retains its pipeline and buffer bindings, geometry and barrier state, while its cached **partial-grid** native records are discarded and rematerialized when executed. A uniform command copied in the same range retains its existing qualified record ownership, as before.

This is a CPU snapshot in an adapted application. It is not `copyIndirectCommandBuffer` on the GPU timeline, native Apple ICB identity, support for arbitrary shaders, or transparent application integration. The existing certified library, same-scope, resource, geometry and serial-range limits remain in force. GPU-selected and reusable-context commands remain refused. Externally synchronize command mutation and keep buffer contents valid until completion. A failed encoding still requires discarding the uncommitted command buffer.

## GTX evidence

The source range is first materialized without submitting a user shader, then copied; the source is reset before executing the destination. The independent CPU oracle checks source and output data, counters, guards, ordering, cache reuse, reset/re-encoding and scope restoration before the final commit. It observes fresh partial-record materialization for the destination. Four scenarios cover partial/partial, partial/uniform, uniform/partial and a 3D partial/partial range at the existing 16-launch limit. Each execution scenario is repeated.

The 12 snapshot hosts cover **72 logical dispatches, 12,114 invocations and 48,456 output words**, including 16 omission/order controls and 48 refusal observations. Four hosts are preparation-only. Six additional hosts qualify the older chain, barrier and uniform paths using the same seven-object runtime; the default-disabled partial-copy refusal remains exercised in the barrier tests. The [independent audit](partial-snapshot-validation.json) rechecks all 18 signed, terminal, nonoverlapping hosts and the raw results. A separate rebuild from the same sources has seven identical object members; its archive container hash differs and the rebuild itself was not GPU-tested. The targeted 31 CPU tests pass.

The first snapshot verifier covered the two all-partial cases. Before the mixed cases, it was extended to account for the unchanged uniform-record reuse; the auditor verifies the exact source difference and separately re-runs each frozen verifier. No results were reassigned across builds. An initial offline aggregate auditor assumed every verifier used a `status` key; barrier results use `verification`, so that audit failed and was corrected and rerun without repeating GPU work.

No speedup, complete Metal conformance or system-driver change is claimed. The cooperative GPU reservation does not exclude unrelated workloads.

## Reproduction

Use the pinned `STENCIL`, `WIDE` and `GRIDLIB` libraries and lab reservation `LAB` from [the prior range qualification](PARTIAL_ICB_CHAINED_RANGE.md), current GPU registry ID `RID`, and fresh output directories. Never overlap GPU hosts or retry an unresolved process. The previous versions of the verifier are retained in their original laboratory builds; new reproductions use the current verifier for all four cases.

```sh
set -e
python3 tools/build_from_source.py --out build/partial-snapshot-new
ARCHIVE="$PWD/build/partial-snapshot-new"
python3 bridge/tools/partial_snapshot.py build --out "$LAB/results/snapshot-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 1 2 3; do
  for kind in prepare execute repeat; do
    mode=execute; [ "$kind" = prepare ] && mode=prepare
    python3 bridge/tools/partial_snapshot.py run --build "$LAB/results/snapshot-build-new" \
      --out "$LAB/results/snapshot-$kind$n-new" --reservation-root "$LAB" --mode "$mode" --case-index "$n" --registry-id "$RID"
  done
done
python3 bridge/tools/partial_range_chain.py build --out "$LAB/results/snapshot-chain-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do python3 bridge/tools/partial_range_chain.py run --build "$LAB/results/snapshot-chain-build-new" --out "$LAB/results/snapshot-chain$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID"; done
python3 bridge/tools/partial_chain_barrier.py build --out "$LAB/results/snapshot-barrier-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
for n in 0 6; do python3 bridge/tools/partial_chain_barrier.py run --build "$LAB/results/snapshot-barrier-build-new" --out "$LAB/results/snapshot-barrier$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID"; done
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/snapshot-uniform-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
for form in groups threads; do python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/snapshot-uniform-build-new" --out "$LAB/results/snapshot-uniform-$form-new" --reservation-root "$LAB" --mode execute --form "$form" --registry-id "$RID"; done
python3 tools/build_from_source.py --out build/partial-snapshot-rebuild-new
python3 bridge/tools/audit_partial_snapshot.py --snapshot \
  "$LAB/results/snapshot-prepare0-new" "$LAB/results/snapshot-execute0-new" "$LAB/results/snapshot-repeat0-new" \
  "$LAB/results/snapshot-prepare1-new" "$LAB/results/snapshot-execute1-new" "$LAB/results/snapshot-repeat1-new" \
  "$LAB/results/snapshot-prepare2-new" "$LAB/results/snapshot-execute2-new" "$LAB/results/snapshot-repeat2-new" \
  "$LAB/results/snapshot-prepare3-new" "$LAB/results/snapshot-execute3-new" "$LAB/results/snapshot-repeat3-new" \
  --chain "$LAB/results/snapshot-chain0-new" "$LAB/results/snapshot-chain3-new" \
  --barrier "$LAB/results/snapshot-barrier0-new" "$LAB/results/snapshot-barrier6-new" \
  --uniform "$LAB/results/snapshot-uniform-groups-new" "$LAB/results/snapshot-uniform-threads-new" \
  --current-source-build "$PWD/build/partial-snapshot-rebuild-new" --out "$LAB/results/snapshot-audit-new.json"
python3 -m unittest discover -s tests -p 'test_partial*.py' -v
```

Proprietary libraries and raw captures are not distributed; obtain or regenerate local prerequisites under their publishers' terms.
