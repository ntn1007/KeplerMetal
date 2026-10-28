# Revocation witness with a real reusable ICB plan

This is an isolated extension of [the lease-instance experiment](REUSABLE_REVOKE_WITNESS.md). It tests the current seven-object runtime and a real `KPGPUCommandSelection`, registered native producer and reusable destination ICB. The test does **not** add a public cancellation operation.

In the first generation, the modified laboratory client reserves a retained command buffer in the actual plan and records its real producer. Reset of the target ICB is refused while that buffer is pending. A per-instance subclass then refuses ordinary `commit` and `enqueue` on that buffer. The test manually removes the buffer from the lease's private `pending` dictionary and clears the plan's private `producerBuffer` using KVC. The ordinary client then reserves a new producer, runs the producer, materializer and consumer, and completes four generations reusing the same context. Ordinary submission of the old buffer remains refused before and after the ordinary scope's `restore`.

The first pilot cleared only `pending`; its second producer reservation was refused with `Reusable producer reservation is unavailable` and exit 32. The real plan independently retains its original producer. This is an expected consequence of the current implementation, not a driver failure. The pilot's terminal receipt and output are preserved. The second version's KVC reset is strictly test instrumentation, not a supported way to abandon an ICB submission.

## Evidence

The [audit](reusable-plan-revoke-validation.json) verifies one unchanged native-control process, the refused pilot, and two successful witness processes: all four are signed, terminal and nonoverlapping under the shared laboratory reservation. The pinned runtime archive SHA-256 is `0275b13126a63372518b85fcd8e546af0cae0b593ceb37cadc5574b4a765d85a`.

The two witnesses together cover eight real ICB generations and **915,456 exact consumer uint32 values**, with 10,105,984 guard bytes verified. The CPU oracle checks the native producer, generated records and consumer outputs; 32 corresponding stage/counter files match the independent unmodified-client control. The auditor also regenerates the derived client from its pinned base source, checks the source and executable digests, and reruns the numerical oracle on the stored captures. The refused pilot does not contribute to the success counts.

The test runtime is freshly rebuilt from public sources; its source manifest and the six locally obtained pinned assets are checked by the existing builder. One earlier attempt to use a historical archive was refused before build or GPU execution because its sources no longer matched the current tree. The new build, commands, raw data and failed pilot remain in the private laboratory; proprietary artifacts are not included here.

## Limits and next work

The experiment is cooperative and process-local. It **does not** make manual mutation safe for applications, and the installed runtime still prohibits cancellation. The witness does not cover multiple real plans sharing a buffer, automatic queue/factory class restoration, cached IMPs, concurrent submissions, callbacks and deallocation, error recovery or arbitrary application behavior. The tested `restore` is the ordinary scope in this client; automatic command-buffer factories were not enabled. The original producer is not submitted, so the guard is observed through normal Objective-C calls and retained `NotEnqueued` status, not by independently reading resident GPU instructions.

An actual implementation would need an explicit ownership contract, atomic coordination of all affected leases and plan state, robust lifetime handling and failure paths, and the complete affected GPU regression suite. This result does not establish transparent Metal support, general cancellation, a performance gain, video decoding or an installed-driver change.

## Re-audit recorded evidence

The following reads the existing private outputs; it does not launch GPU work. The auditor pins this exact build and must be reviewed and adapted to verify a new build.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
python3 bridge/experiments/reusable_plan_revoke/audit.py \
  --build "$R/real-icb-revoke-witness-build-20261028-02" \
  --pilot-build "$R/real-icb-revoke-witness-build-20261028-01" \
  --runs "$R/real-icb-revoke-native-control-20261028-01" \
    "$R/real-icb-revoke-witness-run-20261028-01" \
    "$R/real-icb-revoke-witness-run-20261028-02" \
    "$R/real-icb-revoke-witness-run-20261028-03" \
  --out "$R/real-icb-revoke-reaudit-new.json"
python3 -m unittest discover -s tests -p 'test_reusable_plan_revoke.py' -v
```

To regenerate the base, follow [REUSABLE_ICB_CONTEXTS.md](REUSABLE_ICB_CONTEXTS.md) with `--function-arguments --stable-identities --reusable-contexts`, a fresh complete source build, and the six exact local assets. `experiment.py build` records and signs a derived client; `experiment.py run` verifies frozen inputs and uses the shared GPU reservation. Never retry a process until its terminal state is established.
