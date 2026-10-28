# Object-based GPU ICB copying in a public Metal client

This page records the earlier single-client qualification. A later [local-policy experiment](STANDALONE_COPY_POLICY.md) tests the same path with two related clients.

A separately linked public-Metal test client now copies and executes a bounded mixed partial/uniform project ICB **without labelling its command buffer**. An explicit process-local bootstrap still accepts only one pinned executable, GTX, dual-function library and manifest. It adapts blit encoder instances on the scope's queue and identifies project ICB objects at the public copy selector. Ordinary buffer blits use their native implementation; the wrapper restores the native encoder class after `endEncoding`. No shared native class, system framework or driver is modified.

The new scope method `prepareExperimentalPartialGPUCopyFrom:sourceRange:destination:destinationIndex:error:` validates the entire range before preparing any slot: scope, bounds, nonoverlap, original CPU-owned state, matching per-pair registered pipelines and geometry, resource envelopes and the eight-QMD limit. It requires at least one partial slot. After successful preflight it prepares the required partial and uniform records, which can submit bounded native initialization/NOP/blit work and wait; no user shader is dispatched by preparation. The copy path rechecks the initialized records, retains their owners and submits one Metal buffer blit per QMD. The bootstrap detaches the ended adapted blit encoder through the new explicitly scoped detach method. The test checks restoration of both an ordinary and an adapted blit encoder.

The runtime accepts bounded nonoverlapping source and destination offsets; this cohort tests `(0, 0)` in 1D and `(1, 2)` in 3D, each for two commands. On the same encoder the bootstrap refuses a second project-ICB copy. The client must synchronize resource contents and CPU mutation, end encoders and discard command buffers after a failure. Preparation waits on the scope queue; the caller must not create cyclic dependencies on an uncommitted buffer. Other layouts, ranges, independent applications, shaders and concurrent queue use remain unqualified.

## GTX evidence

Thirteen new signed processes cover two repetitions each for same-buffer and committed-predecessor same-queue execution in 1D and 3D, two native missing-ICB controls and three wrong-client, wrong-manifest or wrong-library refusals. The eight positive executions submit **32 QMD buffer blits**, execute **16 logical dispatches / 1,368 shader invocations** and produce **8,208 CPU-verified 32-bit output words**. A partial barrier shader produces coordinates and geometry; a uniform second shader consumes the coordinates. Counter values, untouched destination buffers and guards are checked. The four separate-buffer cases refuse an uncommitted predecessor.

Each positive process refuses an invalid overflowing range, an overlapping self-copy, an unretained command buffer, a nine-region copy and mismatched geometry. The trace confirms no native command materialization for the four preflight failures; the unretained buffer is refused before preflight. Each also refuses a second project copy in the same blit encoder. The code performs all range checks before initiating preparation; later preparation failures may still leave initialized intermediate records, so the caller discards the failing buffer.

Seven further **new** same-runtime processes recheck the earlier labelled public-client copy, standalone compute client, standalone render client and explicit GPU-copy path. The [audit](standalone-automatic-copy-validation.json) verifies all 20 signed, nonoverlapping processes, frozen sources, terminal reservations, CPU results, QMD addresses, native profiles and seven object members in an independent rebuild. [Offline mutations](standalone-automatic-copy-mutation.json) reject eleven altered evidence cases while the untouched case passes. The full CPU suite reports 500 tests with one skipped.

This is a pinned test process with explicit bootstrap injection, not a general Metal ICB implementation or transparent system driver. The common GPU reservation coordinates participating runners only, not WindowServer or unrelated processes. No speedup is claimed; no system driver, OCLP, framework or firmware was changed.

## Reproduction

Use pinned local `DUAL` and `STENCIL` libraries, a common reservation root `LAB`, and the current GTX registry ID `RID` as described in [the preceding copy qualification](STANDALONE_PARTIAL_COPY.md). Use fresh paths; never retry while a process or reservation remains unresolved. Proprietary inputs and raw captures remain local.

```sh
set -e
python3 tools/build_from_source.py --out build/standalone-auto-copy-new
ARCHIVE="$PWD/build/standalone-auto-copy-new"
python3 bridge/experiments/standalone_automatic_copy/experiment.py build --out "$LAB/results/auto-copy-build-new" --library "$ARCHIVE" --metallib "$DUAL"
for n in 0 3; do
  python3 bridge/experiments/standalone_automatic_copy/experiment.py run --build "$LAB/results/auto-copy-build-new" --out "$LAB/results/auto-copy-native-$n-new" --reservation-root "$LAB" --mode native --scenario "$n" --route same --registry-id "$RID"
  for route in same separate; do for trial in first repeat; do python3 bridge/experiments/standalone_automatic_copy/experiment.py run --build "$LAB/results/auto-copy-build-new" --out "$LAB/results/auto-copy-$route-$trial-$n-new" --reservation-root "$LAB" --mode auto --scenario "$n" --route "$route" --registry-id "$RID"; done; done
done
for mode in wrong-client wrong-manifest wrong-library; do python3 bridge/experiments/standalone_automatic_copy/experiment.py run --build "$LAB/results/auto-copy-build-new" --out "$LAB/results/auto-copy-$mode-new" --reservation-root "$LAB" --mode "$mode" --scenario 0 --route same --registry-id "$RID"; done
python3 bridge/experiments/standalone_partial_copy/experiment.py build --out "$LAB/results/auto-copy-labelled-build-new" --library "$ARCHIVE" --metallib "$DUAL"
python3 bridge/experiments/standalone_partial_copy/experiment.py run --build "$LAB/results/auto-copy-labelled-build-new" --out "$LAB/results/auto-copy-labelled-0-new" --reservation-root "$LAB" --mode auto --scenario 0 --route same --registry-id "$RID"
python3 bridge/experiments/standalone_partial_copy/experiment.py run --build "$LAB/results/auto-copy-labelled-build-new" --out "$LAB/results/auto-copy-labelled-3-new" --reservation-root "$LAB" --mode auto --scenario 3 --route separate --registry-id "$RID"
python3 bridge/experiments/standalone_partial_compute/experiment.py build --out "$LAB/results/auto-copy-compute-build-new" --library "$ARCHIVE" --metallib "$DUAL"
for n in 0 3; do python3 bridge/experiments/standalone_partial_compute/experiment.py run --build "$LAB/results/auto-copy-compute-build-new" --out "$LAB/results/auto-copy-compute-$n-new" --reservation-root "$LAB" --mode auto --scenario "$n" --registry-id "$RID"; done
python3 bridge/experiments/standalone_icb/experiment.py build --out "$LAB/results/auto-copy-render-build-new" --library "$ARCHIVE"
python3 bridge/experiments/standalone_icb/experiment.py run --build "$LAB/results/auto-copy-render-build-new" --out "$LAB/results/auto-copy-render-new" --reservation-root "$LAB" --mode auto
python3 bridge/tools/partial_gpu_mixed_copy.py build --out "$LAB/results/auto-copy-explicit-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do python3 bridge/tools/partial_gpu_mixed_copy.py run --build "$LAB/results/auto-copy-explicit-build-new" --out "$LAB/results/auto-copy-explicit-$n-new" --reservation-root "$LAB" --mode same --case-index "$n" --registry-id "$RID"; done
python3 tools/build_from_source.py --out build/standalone-auto-copy-rebuild-new
python3 bridge/experiments/standalone_automatic_copy/audit.py \
  --hosts "$LAB"/results/auto-copy-native-{0,3}-new "$LAB"/results/auto-copy-{same,separate}-{first,repeat}-{0,3}-new "$LAB"/results/auto-copy-{wrong-client,wrong-manifest,wrong-library}-new \
  --labelled "$LAB"/results/auto-copy-labelled-{0,3}-new --compute "$LAB"/results/auto-copy-compute-{0,3}-new --render "$LAB/results/auto-copy-render-new" --copy "$LAB"/results/auto-copy-explicit-{0,3}-new \
  --current-source-build "$PWD/build/standalone-auto-copy-rebuild-new" --out "$LAB/results/auto-copy-audit-new.json"
python3 bridge/experiments/standalone_automatic_copy/mutate.py --same "$LAB/results/auto-copy-same-first-0-new" --separate "$LAB/results/auto-copy-separate-first-0-new" --wrong-client "$LAB/results/auto-copy-wrong-client-new"
python3 -m unittest discover -s tests
```
