# Two scoped GPU ICB copies per encoder

This separate experiment extends the [local policy bootstrap](STANDALONE_COPY_POLICY.md) to allow up to two copies between disjoint pairs of project ICBs within one blit encoder. Each copy independently passes the existing whole-range preflight and prepares its own native descriptors. The encoder retains its ICB identities; a second use of any first-pair ICB and a third project copy are refused before preparation. An unsuccessful encoding requires discarding the command buffer. The caller must synchronize mutation and avoid cyclic GPU queue waits. ICB identity checks do not establish general resource-alias safety.

This is a process-local opt-in bootstrap for exactly the registered two-shader profile on the GTX. It is not native ICB support, general Metal compatibility, transparent system integration, or a driver upgrade. Mixed project/native ICB copies, other shader profiles, GPU-selected commands, multiple queues and arbitrary dependencies remain outside this qualification. The existing one-copy experiment remains unchanged.

## Evidence and limits

Thirteen fresh, signed, nonoverlapping processes were audited. Eight positive processes exercised two disjoint copies with 1D and 3D geometries, each repeated for same-command-buffer and separately committed same-queue execution. Each source was reset before the consumer ran. Each process also encoded one copy into a separate uncommitted command buffer, verified that repeating its ICB pair was refused, and discarded that buffer. Guards, counters and both output sets were checked against a CPU oracle. Two additional processes exercised the prior one-copy client. The three other processes checked native missing ICB, a wrong policy and a wrong shader library.

Across the ten positive processes the audit counts **72 committed GPU descriptor blits, 36 logical dispatches, 3,078 shader invocations and 18,468 exact 32-bit output words**. These are test counts, not a performance benchmark. An [audit](standalone-multi-copy-validation.json) rechecks frozen sources, signatures, reservations, CPU results, nonoverlap and the seven object members of an independently built runtime. The [mutation check](standalone-multi-copy-mutation.json) rejects eight deliberately altered evidence cases offline. The original discarded dependent-copy control is not counted among the committed blits. This does not qualify a third-copy test, arbitrary resource aliasing or third-party clients.

The reservation coordinates participating laboratory runners, not unrelated processes or WindowServer. Tests were done without changing the installed driver, OCLP, frameworks or firmware. No speedup is claimed.

## Reproduction

Use the pinned local `DUAL` metallib, common laboratory reservation root `LAB` and current GTX registry ID `RID` from [the preceding experiment](STANDALONE_AUTOMATIC_COPY.md). Supply fresh output paths and never retry an unresolved reservation. Neither vendor binaries nor raw captures are distributed.

```sh
set -e
python3 tools/build_from_source.py --out build/multi-copy-source-new
python3 tools/build_from_source.py --out build/multi-copy-rebuild-new
EXP=bridge/experiments/standalone_multi_copy_policy
python3 "$EXP/experiment.py" build --out "$LAB/results/multi-copy-build-new" --library "$PWD/build/multi-copy-source-new" --metallib "$DUAL"
for n in 0 3; do
  for route in same separate; do
    for rep in first repeat; do
      python3 "$EXP/experiment.py" run --build "$LAB/results/multi-copy-build-new" --out "$LAB/results/multi-copy-a-$n-$route-$rep-new" --reservation-root "$LAB" --mode optin-a --scenario "$n" --route "$route" --registry-id "$RID"
    done
  done
done
python3 "$EXP/experiment.py" run --build "$LAB/results/multi-copy-build-new" --out "$LAB/results/multi-copy-b-0-new" --reservation-root "$LAB" --mode optin-b --scenario 0 --route same --registry-id "$RID"
python3 "$EXP/experiment.py" run --build "$LAB/results/multi-copy-build-new" --out "$LAB/results/multi-copy-b-3-new" --reservation-root "$LAB" --mode optin-b --scenario 3 --route separate --registry-id "$RID"
for mode in native-a wrong-policy wrong-library; do
  python3 "$EXP/experiment.py" run --build "$LAB/results/multi-copy-build-new" --out "$LAB/results/multi-copy-$mode-new" --reservation-root "$LAB" --mode "$mode" --scenario 0 --route same --registry-id "$RID"
done
python3 "$EXP/audit.py" --build "$LAB/results/multi-copy-build-new" --source-build "$PWD/build/multi-copy-rebuild-new" --out "$LAB/results/multi-copy-audit-new.json" --hosts "$LAB"/results/multi-copy-a-{0,3}-{same,separate}-{first,repeat}-new "$LAB"/results/multi-copy-b-{0,3}-new "$LAB"/results/multi-copy-{native-a,wrong-policy,wrong-library}-new
python3 "$EXP/mutate.py" --optin "$LAB/results/multi-copy-a-0-same-first-new"
```
