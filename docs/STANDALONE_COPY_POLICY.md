# A local policy for scoped GPU ICB copies

The process-local GPU-copy bootstrap can now read a local policy of up to 16 distinct lowercase executable SHA-256 values instead of embedding one executable hash when compiled. It checks the policy snapshot against the hash supplied by the launcher, then accepts only a listed executable. The GTX identity, dual-function metallib, manifest, resource envelopes, queue, geometry and command checks remain unchanged. The same signed bootstrap was used with an A-only policy and an A+B policy, and both clients were executed using the same A+B policy without rebuilding the bootstrap.

The policy and expected hash are both chosen by the launcher. This is **not a digital signature or independent security authority**: a caller who controls both can choose another list. A listed hash does not certify a client's shader use or behavior. The two clients are distinct but related purpose-built public-Metal test programs derived from previous project witnesses. They are not independent third-party applications. One uses no command-buffer label and the other retains a label that the bootstrap ignores. Both are limited to the exact registered shaders and bounded command profile. This remains explicit process-local injection, not a system driver or transparent application support.

## GTX evidence

Eighteen new processes cover two native missing-ICB controls, ten successful opt-in executions and six rejected client, policy, manifest or library cases. The successful executions use both clients, with 1D same-buffer and 3D separately committed same-queue routes; they submit **40 QMD buffer blits**, execute **20 logical dispatches / 1,710 shader invocations**, and produce **10,260 CPU-verified 32-bit output words**. Source/destination outputs, counters and guards are checked. The B client is rejected by the A-only policy; an altered policy and a correctly hashed policy containing a duplicate are refused. The A+B policy successfully admits both clients.

The [audit](standalone-copy-policy-validation.json) checks those 18 signed processes and four **previously captured** same-runtime controls, their frozen sources, executable and bootstrap hashes, policies, CPU oracles, terminal reservations and nonoverlapping intervals. It compares all seven object members against an independently rebuilt runtime. [Offline mutations](standalone-copy-policy-mutation.json) reject eleven altered evidence cases while the untouched case passes. The current targeted CPU suite reports 31 tests passing. The common GPU reservation coordinates participating runners only, not WindowServer or unrelated processes.

The policy does not expand support for arbitrary shaders, GPU-selected commands, multiple queues, chained copies or hardened applications. Preparation can submit bounded internal initialization work and wait. The caller must synchronize resource mutation and discard an uncommitted buffer after a failed encode. No speedup is claimed. No system driver, framework, OCLP or firmware was modified.

## Reproduction

Use pinned local `DUAL`, the common reservation root `LAB` and current GTX registry ID `RID` as in [the previous qualification](STANDALONE_AUTOMATIC_COPY.md). Choose fresh paths; never retry an unresolved process or reservation. No proprietary binaries are published.

```sh
set -e
python3 tools/build_from_source.py --out build/standalone-copy-policy-new
ARCHIVE="$PWD/build/standalone-copy-policy-new"
python3 bridge/experiments/standalone_auto_copy_policy/experiment.py build --out "$LAB/results/copy-policy-build-new" --library "$ARCHIVE" --metallib "$DUAL"
for tag in a b; do
  python3 bridge/experiments/standalone_auto_copy_policy/experiment.py run --build "$LAB/results/copy-policy-build-new" --out "$LAB/results/copy-policy-native-$tag-new" --reservation-root "$LAB" --mode "native-$tag" --scenario 0 --route same --registry-id "$RID"
  for trial in first repeat; do
    python3 bridge/experiments/standalone_auto_copy_policy/experiment.py run --build "$LAB/results/copy-policy-build-new" --out "$LAB/results/copy-policy-$tag-$trial-0-new" --reservation-root "$LAB" --mode "optin-$tag" --scenario 0 --route same --registry-id "$RID"
    python3 bridge/experiments/standalone_auto_copy_policy/experiment.py run --build "$LAB/results/copy-policy-build-new" --out "$LAB/results/copy-policy-$tag-$trial-3-new" --reservation-root "$LAB" --mode "optin-$tag" --scenario 3 --route separate --registry-id "$RID"
  done
done
for mode in denied-b wrong-policy malformed-policy wrong-client wrong-manifest wrong-library; do python3 bridge/experiments/standalone_auto_copy_policy/experiment.py run --build "$LAB/results/copy-policy-build-new" --out "$LAB/results/copy-policy-$mode-new" --reservation-root "$LAB" --mode "$mode" --scenario 0 --route same --registry-id "$RID"; done
for n in 0 3; do route=same; if [ "$n" = 3 ]; then route=separate; fi; python3 bridge/experiments/standalone_auto_copy_policy/same_policy.py --build "$LAB/results/copy-policy-build-new" --out "$LAB/results/copy-policy-a-ab-$n-new" --reservation-root "$LAB" --scenario "$n" --route "$route" --registry-id "$RID"; done
python3 bridge/experiments/standalone_automatic_copy/experiment.py build --out "$LAB/results/copy-policy-previous-build-new" --library "$ARCHIVE" --metallib "$DUAL"
for n in 0 3; do route=same; if [ "$n" = 3 ]; then route=separate; fi; for trial in first repeat; do python3 bridge/experiments/standalone_automatic_copy/experiment.py run --build "$LAB/results/copy-policy-previous-build-new" --out "$LAB/results/copy-policy-previous-$trial-$n-new" --reservation-root "$LAB" --mode auto --scenario "$n" --route "$route" --registry-id "$RID"; done; done
python3 tools/build_from_source.py --out build/standalone-copy-policy-rebuild-new
python3 bridge/experiments/standalone_auto_copy_policy/audit.py --build "$LAB/results/copy-policy-build-new" \
  --hosts "$LAB"/results/copy-policy-native-{a,b}-new "$LAB"/results/copy-policy-{a,b}-{first,repeat}-{0,3}-new "$LAB"/results/copy-policy-{denied-b,wrong-policy,malformed-policy,wrong-client,wrong-manifest,wrong-library}-new \
  --same-policy-a "$LAB"/results/copy-policy-a-ab-{0,3}-new --previous "$LAB"/results/copy-policy-previous-{first,repeat}-{0,3}-new \
  --current-source-build "$PWD/build/standalone-copy-policy-rebuild-new" --out "$LAB/results/copy-policy-audit-new.json"
python3 bridge/experiments/standalone_auto_copy_policy/mutate.py --optin "$LAB/results/copy-policy-a-first-0-new" --denied "$LAB/results/copy-policy-denied-b-new"
python3 -m unittest discover -s tests -p 'test_partial*.py'
```
