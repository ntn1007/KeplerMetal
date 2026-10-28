# Instance-local revocation of an uncommitted Metal command buffer

Reusable CommandIR contexts currently retain an uncommitted command buffer as pending because it might still be committed. There is no cancellation API in that implementation. This **separate laboratory witness** investigates one necessary mechanism for a future explicit abandonment operation; it does not change or cancel a real ICB lease.

In its own process, the witness encodes a known compute command into a retained, uncommitted native command buffer. It checks the exact `NVMTLCommandBuffer` class and size, public method encodings, queue profile and status, then changes that one object's class to a temporary subclass that refuses ordinary `commit` and `enqueue` messages. Both calls are caught and the command buffer remains not enqueued. The witness submits a new, independent command buffer that uses the same output resource, checks the GPU result, and tries `commit` on the revoked buffer again.

## Evidence

The [six-process audit](uncommitted-revoke-validation.json) checks the pinned build and sources, signatures, terminal and nonoverlapping shared-reservation receipts, raw results and a CPU oracle:

- Two revoked processes refuse both submission methods and a later repeated `commit`; a new buffer then produces **8,192 correct GPU words** in total. The revoked buffer retains Metal status `NotEnqueued` (0).
- Two native controls submit the original command and produce another **8,192 correct words**. Revocation of a completed buffer is refused.
- Two no-dispatch controls preserve **8,192 sentinel words**. All 192 boundary guard words across six captures match. These controls do not prove the absence of unrelated internal GPU work.

The private profile, output buffer and command queue belong to the test process. The usual shared reservation coordinates participating project processes, not WindowServer. No performance result, video decoding, general ICB support or driver installation is claimed. The class substitution affects a single own-process object and does not modify native class methods, macOS, the driver, OCLP or firmware.

## What this does not establish

This is **not** an ICB cancellation API or a complete solution to the pending-lease problem. It does not test actual `KPReusableIRContext` instances, multiple contexts sharing one command buffer, interaction with automatic-factory scope restoration, callback lifetime, object deallocation, or a real application's lifecycle. An already cached native implementation pointer, a direct bypass, another party changing the object's class or an uncoordinated thread can evade the witness's method overrides. Installing the subclass while another thread invokes the object is not qualified. An application-level lock cannot control framework activity or an unrelated writer. The experiment therefore cannot be used as a security boundary or generalized to arbitrary clients.

The current reusable context continues to prohibit cancellation: removing a pending lease while the original buffer can still be submitted is unsafe. Any integration needs a separately designed ownership contract and tests of the actual context, revocation lifetime and cleanup, failure paths and the complete affected GPU regressions.

## Re-audit

This re-reads the retained cohort and does not submit GPU work. It requires the private lab, exact build and profile; a changed input is refused. To run new hosts, use the experiment builder and fresh result directories under the same cooperative reservation, and do not retry an unresolved process.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
python3 bridge/experiments/uncommitted_revoke/audit.py \
 --build "$R/uncommitted-revoke-build-20261028-01" \
 --out "$R/uncommitted-revoke-audit-new.json" --runs \
 "$R/uncommitted-revoke-negative-1-20261028" "$R/uncommitted-revoke-native-1-20261028" \
 "$R/uncommitted-revoke-revoked-1-20261028" "$R/uncommitted-revoke-native-2-20261028" \
 "$R/uncommitted-revoke-negative-2-20261028" "$R/uncommitted-revoke-revoked-2-20261028"
python3 -m unittest discover -s tests -p 'test_uncommitted_revoke_audit.py' -v
```

The build-input SHA-256 is `7aa93065ee56940e3788a5e2b3d1bebe1c0fdf2f44d03f1b6cc7418aada37b68`. Verifier tests reject changed submission status, missing refusals, stale-write values and altered guards.
