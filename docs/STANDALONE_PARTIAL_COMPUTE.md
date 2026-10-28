# Public Metal client with a scoped partial-compute ICB

A separately compiled client, linked only to Metal and Foundation, now creates and executes a bounded two-command compute ICB using ordinary public Metal calls. It does not import or call KeplerMetal APIs. An explicit launcher injects a project bootstrap into that one test process; the bootstrap verifies the signed executable, an exact dual-function metallib, its manifest and the GTX identity, then installs a process-local scope on one queue. The new `enableAutomaticComputeEncoderFactoriesWithError:` scope opt-in exposes the existing queue-local compute-factory adapter without modifying shared native classes.

The pinned client builds two ordinary compute pipeline states from the registered library and encodes a partial `partial_builtin_barrier` producer followed by a uniform `partial_buffer_stencil` consumer. The bootstrap supplies the corresponding scope-owned pipelines for those exact verified functions. The partial grid is expanded into bounded resident commands, and the results of the barrier producer feed the consumer. This is a purpose-built test client with a process-local bootstrap, not a general-purpose driver or unmodified third-party application. It does **not** exercise GPU-timeline ICB copying; that still requires explicit preparation and scoped blit adaptation.

## GTX evidence

Two 1D and two 3D positive processes execute **8 logical dispatches and 684 shader invocations**, checking **4,104 32-bit output words** against a CPU oracle, as well as the output buffers, counters and guard regions. The oracle also checks the native pipeline names and register profiles, automatic-factory events, signatures, raw outputs and terminal reservations. Two native controls without injection stop at the missing internal ICB selector before user dispatch. Three further controls reject a modified client, manifest or shader library; no user kernel is submitted in those controls.

Three new same-runtime regression processes recheck the earlier public-Metal render client (12,288 float channels) and the mixed GPU-copy path (342 invocations). The [audit](standalone-partial-compute-validation.json) checks all 12 processes, their frozen sources, signatures, nonoverlapping intervals, public-client imports and seven object members in an independent rebuild. [Offline mutations](standalone-partial-compute-mutation.json) reject seven altered cases while the untouched evidence passes. The full CPU suite reports 500 tests with one skipped. A [separate archive-rebuilt client](standalone-partial-compute-rebuilt-client.json) also passes one additional 1D GPU run (192 invocations, 1,152 output words) and one native control; these are not included in the preceding totals.

The launcher and hooks are limited to one approved test executable, one registration, one GTX and one queue. Other applications, shader libraries, pipeline factories, ICB GPU copies, multiple queues, hardened processes and general Metal ICB behavior remain unqualified. Caller resource synchronization remains necessary. The GPU reservation coordinates participating runners, not WindowServer or unrelated processes. No performance comparison or gain is claimed. No system driver, framework, OCLP or firmware was modified.

## Reproduction

Use the pinned local `DUAL` and `STENCIL` libraries described by [the dual-pipeline qualification](PARTIAL_ICB_DUAL_PIPELINE.md), the common reservation root `LAB`, and the current GTX registry ID `RID`. The runner builds a deliberately different valid library and checks client, library and manifest identities. Choose fresh paths; never retry while a previous process or reservation remains unresolved. Proprietary inputs and raw captures remain local.

```sh
set -e
python3 tools/build_from_source.py --out build/standalone-partial-compute-new
ARCHIVE="$PWD/build/standalone-partial-compute-new"
python3 bridge/experiments/standalone_partial_compute/experiment.py build --out "$LAB/results/public-compute-build-new" --library "$ARCHIVE" --metallib "$DUAL"
for n in 0 3; do
  python3 bridge/experiments/standalone_partial_compute/experiment.py run --build "$LAB/results/public-compute-build-new" --out "$LAB/results/public-compute-native-$n-new" --reservation-root "$LAB" --mode native --scenario "$n" --registry-id "$RID"
  for trial in first repeat; do python3 bridge/experiments/standalone_partial_compute/experiment.py run --build "$LAB/results/public-compute-build-new" --out "$LAB/results/public-compute-auto-$trial-$n-new" --reservation-root "$LAB" --mode auto --scenario "$n" --registry-id "$RID"; done
done
for mode in wrong-client wrong-manifest wrong-library; do python3 bridge/experiments/standalone_partial_compute/experiment.py run --build "$LAB/results/public-compute-build-new" --out "$LAB/results/public-compute-$mode-new" --reservation-root "$LAB" --mode "$mode" --scenario 0 --registry-id "$RID"; done
python3 bridge/experiments/standalone_icb/experiment.py build --library "$ARCHIVE" --out "$LAB/results/public-compute-render-build-new"
python3 bridge/experiments/standalone_icb/experiment.py run --build "$LAB/results/public-compute-render-build-new" --out "$LAB/results/public-compute-render-new" --reservation-root "$LAB" --mode auto
python3 bridge/tools/partial_gpu_mixed_copy.py build --out "$LAB/results/public-compute-copy-build-new" --archive "$ARCHIVE" --metallib "$STENCIL"
for n in 0 3; do python3 bridge/tools/partial_gpu_mixed_copy.py run --build "$LAB/results/public-compute-copy-build-new" --out "$LAB/results/public-compute-copy-$n-new" --reservation-root "$LAB" --mode same --case-index "$n" --registry-id "$RID"; done
python3 tools/build_from_source.py --out build/standalone-partial-compute-rebuild-new
python3 bridge/experiments/standalone_partial_compute/audit.py \
  --hosts "$LAB"/results/public-compute-native-{0,3}-new "$LAB"/results/public-compute-auto-{first,repeat}-{0,3}-new "$LAB"/results/public-compute-{wrong-client,wrong-manifest,wrong-library}-new \
  --render "$LAB/results/public-compute-render-new" --copy "$LAB"/results/public-compute-copy-{0,3}-new \
  --current-source-build "$PWD/build/standalone-partial-compute-rebuild-new" --out "$LAB/results/public-compute-audit-new.json"
python3 bridge/experiments/standalone_partial_compute/mutate.py --auto "$LAB/results/public-compute-auto-first-0-new" --wrong-client "$LAB/results/public-compute-wrong-client-new"
python3 -m unittest discover -s tests
```
