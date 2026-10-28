# Experimental abandonment of one reusable ICB producer

`KPGPUCommandSelection` now exposes `experimentallyAbandonReusableProducer:error:` for a very narrow **cooperative adapted-client** case. It is an extension of the project runtime, not a system Metal method. The client must own and serialize all access to the command buffer, end every encoder before abandonment, submit on its owner thread, and guarantee that no party can invoke a saved native implementation pointer, alter its class or submit it through any other path. The entire command buffer is abandoned, including any unrelated commands it may contain.

The method accepts only the active plan's sole tracked, retained, `NotEnqueued` producer, before materialization, on the plan's owner thread and queue. It refuses if more than one project reusable context tracks that buffer, if the plan has already materialized, if the profile is not the exact `NVMTLCommandBuffer` instance class/size/method encodings, or if another stated precondition fails. No attempt is made to support an automatically adapted command-buffer subclass. The project tracks lease ownership within this linked runtime; a second loaded copy, untracked code and foreign writers are outside this registry and must be excluded by the caller.

On success, ordinary `commit` and `enqueue` messages on that one object raise `KeplerAbandonedCommandBuffer`. The lease registration and plan's producer reference are cleared while holding the context lock, allowing the plan to accept a new producer. The old command buffer must not be used again. If an attempted class transition cannot be verified, the lease stays retained and the caller must treat the old state as unusable; failure does not promise recovery.

This mechanism is **not a security boundary**, arbitrary-command cancellation, a general solution for consumer/materializer buffers or automatic factories, a driver replacement, or support for unmodified applications. Saved IMPs, foreign class changes, uncoordinated threads, hidden owners and more than one runtime copy can bypass the assumptions. A caller unable to guarantee the contract must use the existing completion-before-reuse path. Lifetime and reclamation after dropping an abandoned native buffer, cross-queue use, recovery from GPU errors and transparent integration remain unqualified.

## Validation

The current [evidence](reusable-abandon-api-validation.json) is limited to the recorded native Kepler profile. Two adapted-client GPU processes abandon a real recorded producer and then complete four generations each, with 915,456 exact consumer values and 10,105,984 guard bytes checked. Thirty-two stage/counter files match the regular reusable-client control. The original buffer remains `NotEnqueued`; ordinary `commit` and `enqueue` are refused before and after the ordinary scope restore. Each positive process also refuses an unrelated buffer, a foreign-thread attempt, a repeated abandonment, re-reservation of the abandoned buffer and four completed/materialized attempts.

A separate shared-owner case registers the same real native command buffer in the plan's real context and a manually configured second instance of the same context implementation. It verifies that abandonment is refused and both owners remain registered. It does not test two independently created real ICB plans. The CPU mock contract covers normal completion, late callbacks, owner sweeping and rejection of a nonnative buffer; it is not GPU evidence. The full pre-existing 52-process reusable/native/NAK regression uses the same runtime archive. No new performance benchmark or video test was performed.

## Reproduction

Build from published sources with `tools/build_from_source.py`, then use `bridge/tools/public_native_msl_commands.py build` with `--function-arguments --stable-identities --reusable-contexts --nak-baseline` and the exact local assets documented in [REUSABLE_ICB_CONTEXTS.md](REUSABLE_ICB_CONTEXTS.md). `bridge/experiments/reusable_abandon_api/experiment.py` builds a distinct signed adapted client and runs its `positive` or `shared` scenario under the common lab reservation. `cohort.py` runs the existing 52 cases serially. Always use new output directories and establish the exact process's terminal state before retrying.

The audit pins the recorded build and compares frozen sources, signed processes, raw numerical captures and the existing 52-case oracle. Re-audit the retained files without dispatching GPU work:

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
python3 bridge/experiments/reusable_abandon_api/audit.py \
  --build "$R/reusable-abandon-api-client-build-20261028-02" \
  --library build/reusable-abandon-api-20261028-03 \
  --cohort "$R/reusable-abandon-api-cohort-20261028-01" \
  --shared "$R/reusable-abandon-api-shared-20261028-02" \
  --positive "$R/reusable-abandon-api-positive-20261028-03" \
    "$R/reusable-abandon-api-positive-20261028-04" \
  --out "$R/reusable-abandon-api-reaudit-new.json"
```

The exact build-input and archive hashes are recorded in the audit. A new build requires independently updating and reviewing the auditor's pins; existing captures do not qualify another build.
