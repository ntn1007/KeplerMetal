# Serial ranges combining partial and uniform commands

The opt-in project ICB adapter accepts a serial range containing multiple
CPU-encoded partial-grid commands, and can mix them with uniform commands of
the same certified pipeline. A later separately qualified extension permits the two exact pipelines in one registered library; see [the dual-pipeline qualification](PARTIAL_ICB_DUAL_PIPELINE.md). Empty slots are skipped. The existing NVIDIA
resident transport emits the resulting records in slot order, with the checked
native wait after each physical launch. This is an adapted-process extension,
not the native Apple ICB ABI or transparent support for unmodified apps.

The entire range is checked before any slot is materialized: each occupied
slot must be CPU-owned, use a certified pipeline in the same exact registration, and satisfy
its resource and geometry constraints. At most 16 resident launches in total
are accepted, counting each decomposed partial region and each uniform slot.
The present certified shaders and [resource-window rules](PARTIAL_ICB_VARIABLE_RESOURCES.md)
remain in force. Uniform slots are also bounded by their registration. GPU
generated/reusable/resident-selected commands, concurrent encoders, unqualified
pipelines and command snapshots remain outside this path. The caller must
externally synchronize mutation and retain resource contents until completion.

All records are prepared before the user stream is appended. Later native
packet/profile checks can still fail during preparation or encoding: discard
the uncommitted command buffer after any error. Resource ownership is retained
through the command-buffer completion handler. This serial ordering is stronger
than overlapping dispatches; it is not a performance claim or a proof of the
full Metal memory model.

## Test design

An adapted client records a first stencil command from A to B and a second
from B to C, with an empty slot between them. An independent CPU oracle checks
all input/output and guard bytes, invocation counters, slot-to-launch metadata,
cache reuse, reset/re-encoding and restoring the scope before commit. The
consumer-only and reversed-order controls start with a known B and must differ
from the forward chain. A short later-slot buffer and a range of 18 launches
are refused before any command materialization. The tests cover partial→partial,
partial→uniform and uniform→partial, plus a 3D case with exactly 16 launches.
The previously recorded negative control that refused a partial command next
to an empty slot is historical: that range is now intentionally accepted.

## GTX qualification

Sixteen serialized signed hosts comprise four preparation cases, eight execution
cases (each scenario repeated), two original-barrier regressions and two uniform
regressions. The [independent audit](partial-chain-validation.json) rechecked
**72 logical dispatches, 12,114 chain invocations and 48,456 output words**,
including 16 omission/reversed-order observations. It also checked 24 preflight
refusal observations across preparation and execution hosts, 5,632 barrier
regression invocations and 37,264 uniform regression invocations. These counts
include repetitions; they do not qualify every grid, shader or dependency.

One initial mixed-path preparation was refused by the test harness because its
expected error text did not match the uniform path's actual short-buffer error.
The process terminated without submitting a user command; its evidence is
retained separately. The harness was corrected and the final cohort rerun.
After GPU testing, the public header's comments were updated. A fresh build
from the final source produced a different archive container hash; the audit
extracted and verified that all seven object members were byte-identical to
those in the GPU-tested archive. The only source difference was that comment.

## Reproduction

Set `LAB` to the existing lab and reservation root, `RID` to the current GTX
registry ID, `STENCIL` and `WIDE` to the previously qualified shader libraries,
and `GRIDLIB` to the qualified uniform-grid library. Choose fresh output paths.
Never overlap lab GPU processes; a failed encode requires a discarded buffer.

```sh
python3 tools/build_from_source.py --out build/partial-chain-new
ARCHIVE="$PWD/build/partial-chain-new"
python3 bridge/tools/partial_range_chain.py build --out "$LAB/results/chain-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 1 2 3; do
  python3 bridge/tools/partial_range_chain.py run --build "$LAB/results/chain-build-new" --out "$LAB/results/chain-prepare-$n-new" --reservation-root "$LAB" --mode prepare --case-index "$n" --registry-id "$RID" || break
  python3 bridge/tools/partial_range_chain.py run --build "$LAB/results/chain-build-new" --out "$LAB/results/chain-case-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
  python3 bridge/tools/partial_range_chain.py run --build "$LAB/results/chain-build-new" --out "$LAB/results/chain-repeat-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/partial_chain_barrier.py build --out "$LAB/results/chain-barrier-build-new" --archive "$ARCHIVE" --metallib "$WIDE"
for n in 0 6; do
  python3 bridge/tools/partial_chain_barrier.py run --build "$LAB/results/chain-barrier-build-new" --out "$LAB/results/chain-barrier-$n-new" --reservation-root "$LAB" --mode execute --case-index "$n" --registry-id "$RID" || break
done
python3 bridge/tools/uniform_icb_3d.py build --out "$LAB/results/chain-uniform-build-new" --archive "$ARCHIVE" --metallib "$GRIDLIB"
for form in groups threads; do
  python3 bridge/tools/uniform_icb_3d.py run --build "$LAB/results/chain-uniform-build-new" --out "$LAB/results/chain-uniform-$form-new" --reservation-root "$LAB" --mode execute --form "$form" --registry-id "$RID" || break
done
python3 bridge/tools/audit_partial_range_chain.py \
  --chain "$LAB/results/chain-prepare-0-new" "$LAB/results/chain-prepare-1-new" "$LAB/results/chain-prepare-2-new" "$LAB/results/chain-prepare-3-new" "$LAB/results/chain-case-0-new" "$LAB/results/chain-case-1-new" "$LAB/results/chain-case-2-new" "$LAB/results/chain-case-3-new" "$LAB/results/chain-repeat-0-new" "$LAB/results/chain-repeat-1-new" "$LAB/results/chain-repeat-2-new" "$LAB/results/chain-repeat-3-new" \
  --barrier "$LAB/results/chain-barrier-0-new" "$LAB/results/chain-barrier-6-new" \
  --uniform "$LAB/results/chain-uniform-groups-new" "$LAB/results/chain-uniform-threads-new" --current-source-build "$ARCHIVE"
python3 -m unittest discover -s tests -p test_partial_range_chain_oracle.py -v
```

The library files are obtained locally; this repository does not distribute
Apple or NVIDIA binaries. Preparation uses bounded native NOP and blit work,
but does not dispatch the user shader. Numerical comparison is on the GTX,
not evidence of functionality on other GPU models or system-wide integration.
