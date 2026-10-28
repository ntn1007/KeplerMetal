# Public Metal client with scoped GPU ICB copying

A separately linked Metal/Foundation client now calls the public `copyIndirectCommandBuffer:sourceRange:destination:destinationIndex:` selector, then executes the copied mixed partial/uniform compute commands. It does not import or call KeplerMetal APIs. An explicit process-local bootstrap checks the exact signed client, GTX, dual-function metallib and manifest. It intercepts blit creation only for a command buffer carrying the test label `KeplerMetal pinned ICB copy`; the pinned copy adapter accepts only source range `(0, 2)`, destination index `0` and distinct project ICBs. Other uses and third-party applications are not qualified.

The adapter prepares the partial source/destination slots and their uniform partners, delegates the copy to the established scoped ICB path, and retains records through completion. Preparation may submit internal bounded initialization/NOP/blit work and wait; it does not submit a user shader. A geometry mismatch is refused before the QMD copy is encoded, but **after preparation may already have submitted initialization work**. The client discards the uncommitted failing buffer. The successful copy emits a real Metal buffer blit for each native QMD, resets the source, and executes the destination. The first registered pipeline produces coordinates and a threadgroup-barrier witness; the second consumes the coordinates. The CPU oracle checks both results, counters, guard bytes and unchanged original destination buffers.

## GTX evidence

Thirteen new signed processes cover two 1D and two 3D repetitions for each of the same-buffer and committed-predecessor same-queue routes, two native controls and three rejected client, library or manifest identities. The eight copied executions produce **16 logical dispatches, 1,368 shader invocations, 8,208 verified 32-bit output words and 32 committed QMD buffer blits**. A geometry mismatch is rejected in every positive case; the four separate-buffer cases also reject an uncommitted predecessor. The two native controls stop at the missing internal ICB selector before user dispatch. Identity controls submit no user shader.

The [audit](standalone-partial-copy-validation.json) rechecks these 13 processes and five **previously captured** nonoverlapping controls from the same runtime: public-client compute, public-client rendering and the explicit mixed-copy path. It checks signed binaries, exact frozen source, CPU oracles, source/destination QMD addresses, both pipeline profiles, ordering, terminal reservations and the seven object members of a separate runtime rebuild. [Offline mutations](standalone-partial-copy-mutation.json) reject eight altered evidence cases while the untouched case passes. The current targeted CPU suite passes 31 tests; the unchanged runtime passed 500 tests with one skipped in the preceding qualification.

This is a specific test client and a label-dependent, process-local adapter, not a general Metal ICB implementation, automatic third-party integration or a system driver. Chained copies, cross-queue ordering, other client executables, other buffer layouts and other shaders are unqualified. Caller synchronization of CPU mutation and resource contents is required. Discard a command buffer if encoding fails. The GPU reservation coordinates project runners, not WindowServer or unrelated processes. No speedup is claimed and no system driver, framework, OCLP or firmware was modified.

## Reproduction

Use pinned local `DUAL` and `STENCIL` inputs, a shared reservation root `LAB`, and the current GTX registry ID `RID`, as in [the preceding standalone compute qualification](STANDALONE_PARTIAL_COMPUTE.md). Use fresh paths and never restart while a signed process or reservation remains unresolved. Proprietary inputs and captures remain local.

```sh
set -e
python3 tools/build_from_source.py --out build/standalone-partial-copy-new
ARCHIVE="$PWD/build/standalone-partial-copy-new"
python3 bridge/experiments/standalone_partial_copy/experiment.py build --out "$LAB/results/public-copy-build-new" --library "$ARCHIVE" --metallib "$DUAL"
for n in 0 3; do
  python3 bridge/experiments/standalone_partial_copy/experiment.py run --build "$LAB/results/public-copy-build-new" --out "$LAB/results/public-copy-native-$n-new" --reservation-root "$LAB" --mode native --scenario "$n" --route same --registry-id "$RID"
  for route in same separate; do for trial in first repeat; do python3 bridge/experiments/standalone_partial_copy/experiment.py run --build "$LAB/results/public-copy-build-new" --out "$LAB/results/public-copy-$route-$trial-$n-new" --reservation-root "$LAB" --mode auto --scenario "$n" --route "$route" --registry-id "$RID"; done; done
done
for mode in wrong-client wrong-manifest wrong-library; do python3 bridge/experiments/standalone_partial_copy/experiment.py run --build "$LAB/results/public-copy-build-new" --out "$LAB/results/public-copy-$mode-new" --reservation-root "$LAB" --mode "$mode" --scenario 0 --route same --registry-id "$RID"; done
python3 bridge/experiments/standalone_partial_compute/experiment.py build --out "$LAB/results/public-copy-compute-build-new" --library "$ARCHIVE" --metallib "$DUAL"
for n in 0 3; do python3 bridge/experiments/standalone_partial_compute/experiment.py run --build "$LAB/results/public-copy-compute-build-new" --out "$LAB/results/public-copy-compute-$n-new" --reservation-root "$LAB" --mode auto --scenario "$n" --registry-id "$RID"; done
python3 bridge/experiments/standalone_icb/experiment.py build --library "$ARCHIVE" --out "$LAB/results/public-copy-render-build-new"
python3 bridge/experiments/standalone_icb/experiment.py run --build "$LAB/results/public-copy-render-build-new" --out "$LAB/results/public-copy-render-new" --reservation-root "$LAB" --mode auto
python3 bridge/tools/partial_gpu_mixed_copy.py build --out "$LAB/results/public-copy-prior-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do python3 bridge/tools/partial_gpu_mixed_copy.py run --build "$LAB/results/public-copy-prior-build-new" --out "$LAB/results/public-copy-prior-$n-new" --reservation-root "$LAB" --mode same --case-index "$n" --registry-id "$RID"; done
python3 tools/build_from_source.py --out build/standalone-partial-copy-rebuild-new
python3 bridge/experiments/standalone_partial_copy/audit.py \
  --hosts "$LAB"/results/public-copy-native-{0,3}-new "$LAB"/results/public-copy-{same,separate}-{first,repeat}-{0,3}-new "$LAB"/results/public-copy-{wrong-client,wrong-manifest,wrong-library}-new \
  --compute "$LAB"/results/public-copy-compute-{0,3}-new --render "$LAB/results/public-copy-render-new" --copy "$LAB"/results/public-copy-prior-{0,3}-new \
  --current-source-build "$PWD/build/standalone-partial-copy-rebuild-new" --out "$LAB/results/public-copy-audit-new.json"
python3 bridge/experiments/standalone_partial_copy/mutate.py --same "$LAB/results/public-copy-same-first-0-new" --separate "$LAB/results/public-copy-separate-first-0-new" --wrong-client "$LAB/results/public-copy-wrong-client-new"
python3 -m unittest discover -s tests -p 'test_partial*.py'
```
