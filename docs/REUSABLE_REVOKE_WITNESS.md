# Revocation with two reusable-context lease instances

This isolated witness extends [the native command-buffer revocation test](UNCOMMITTED_REVOKE.md). It compiles the exact current `KeplerReusableIRContext.inc` into the signed test process and manually configures **two instances** on the same queue. Both track the same real, retained, uncommitted native Metal command buffer. Both correctly refuse to become idle while it is pending.

After instance-local revocation refuses ordinary `commit` and `enqueue`, the test **manually removes** the buffer from the first context's pending dictionary. The second context remains busy. The test then manually removes it from the second, retires both, submits a new native GPU command using the same output buffer, and verifies that a later ordinary `commit` on the old command buffer remains refused. These direct dictionary mutations are test instrumentation, not a supported runtime operation. The native control submits the original buffer normally and checks that both real contexts become idle and retire on completion. No actual ICB, reusable generation initialization, or consumer command is involved.

## Evidence

The [audit](reusable-revoke-witness-validation.json) checks six signed, terminal, nonoverlapping processes under the shared reservation, the frozen lease source and binary, and each raw capture against a CPU oracle. Two revoked runs produce 8,192 correct GPU words; two native controls produce 8,192 correct GPU words; two no-dispatch controls preserve 8,192 sentinel words. All 192 guard words match. The test repeats partial removal and the subsequent stale `commit` refusal in the revoked and no-dispatch cases. GPU output demonstrates the subsequent test kernel, not execution of an ICB producer.

The experiment uses `NVMTLCommandBuffer` instance size 656 and verifies its two method encodings before changing that one object's class. It never changes the installed driver, OCLP, system frameworks or shared runtime. The test includes the implementation directly; its instances are manually configured rather than obtained through a real application plan. There is no claim of a complete GPU feature, application integration, speedup or installed-driver repair.

## Remaining work

The experiment does not establish a safe general cancellation API. One command buffer can be owned by multiple contexts, so an implementation must coordinate owners, prevent stale submission throughout their lifetimes, handle the completion handlers and resource retention, and fail closed on partial failure. Restore of automatic factory scopes, cached IMP or direct calls, runtime mutation, concurrent sends, callback release and deallocation are not tested. Revocation is not a security boundary. A later [experimental producer-only operation](REUSABLE_ABANDON_API.md) refuses known multiple ownership under a strict cooperative contract; normal completion remains the supported path outside that contract.

The next validation needs actual ICB plans and generation changes, multiple owners, automatic-scope restoration and lifetime/error cases, followed by the affected complete regression suite. The class substitution alone does not address uncooperative clients or transparent integration.

## Re-audit

This rechecks recorded observations and does not dispatch GPU work. It requires the original local build and results **and a separate checkout of commit `121f427`**, since the current lease implementation has subsequently changed. The auditor intentionally refuses a different source hash. The pinned build-input digest is `df2182b5713c84100123c5e2d0024dd43816e23253cb27626603c8f39ec495db`, and the lease source digest is `ce087c8c5ef335d4aa0ef7b37339df243521093226ceba83a8ed532e738cf301`.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
python3 bridge/experiments/reusable_revoke_witness/audit.py \
  --build "$R/reusable-revoke-witness-build-20261028-01" \
  --out "$R/reusable-revoke-witness-reaudit-new.json" --runs \
  "$R/reusable-revoke-witness-negative-1-20261028" \
  "$R/reusable-revoke-witness-native-1-20261028" \
  "$R/reusable-revoke-witness-revoked-1-20261028" \
  "$R/reusable-revoke-witness-native-2-20261028" \
  "$R/reusable-revoke-witness-negative-2-20261028" \
  "$R/reusable-revoke-witness-revoked-2-20261028"
python3 -m unittest discover -s tests -p 'test_reusable_revoke_witness_audit.py' -v
```

For a new cohort, use `experiment.py build` and `experiment.py run` with fresh directories and the common lab reservation. Build dispatches nothing; each run validates the profile and frozen sources. The audit pins the recorded build and must be independently adapted and reviewed for a newly built artifact.
