# Independent client block behind a scoped no-copy guard

This prototype extends the [client-owned Metal block experiment](NOCOPY_CLIENT_BLOCK.md). The test client's separately compiled block no longer refers to the laboratory's gate, counters or GPU state. The adapted host holds the client block inside a distinct guard block and passes the guard to `newBufferWithBytesNoCopy`. The guard validates one registered address and length, prevents early and repeated delivery, and invokes the retained client block only after the existing three-event laboratory gate permits it. The client block owns the deallocation of its own 4 KiB Mach VM allocation.

On the pinned GTX 880M profile, six signed hosts ran without overlapping GPU reservations. Five hosts each submitted two GPU commands on separate queues; an independent CPU oracle verified 40,960 output words. Three guarded hosts called the independent client once after both commands completed and their output was verified and the observed root deallocation call returned. Each client deallocation succeeded and a VM region query no longer covered the allocation. The retained-buffer, native GPU and rejected-policy controls made no client call. Two late duplicate guard calls were **simulated by the test** and rejected. The audit rejects 54 deliberately altered records.

A separate CPU-only test verifies that the guard retains the independently supplied block through a drained autorelease pool and releases it when the guard is released. It also tests unapproved and incorrect-address calls, one successful release and duplicate suppression. A simulated incomplete-GPU state refuses delivery and permanently consumes the guard: the allocation remains the caller's responsibility. This last test does not execute GPU work.

This is a cooperative, process-local test with one known allocation, a registered callback and two explicitly tracked commands. Metal receives the guard block, not the original client block. The native driver's callback was not observed in the unmodified control; a laboratory action invokes the guard. This is not a transparent fix, an application-facing SDK, evidence that arbitrary deallocators or untracked GPU queues are safe, proof of kernel resource destruction, or a performance claim. The guard's postcondition checks this test's Mach VM unmapping and cannot be generalized to clients whose deallocator has different behavior. No system component is modified.

## Reproduce on the pinned profile

Obtain dependencies as described in [Dependencies](DEPENDENCIES.md), verify the current GTX `nvAccelerator` registry ID and use the cooperative GPU reservation. Each test process owns its own allocation. Run serially and use fresh paths:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified current nvAccelerator registry ID>'
EXP=bridge/experiments/nocopy_gpu_client_guard
python3 "$EXP/experiment.py" build --out "$LAB/results/client-guard-build-new"
for item in hold-nocopy:1 nocopy-gpu:1 nocopy-repair-gpu:1 nocopy-reject-gpu:1 nocopy-repair-gpu-late:1 nocopy-repair-gpu-late:2; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/client-guard-build-new" \
    --out "$LAB/results/client-guard-$mode-$n" --lab "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/client-guard-build-new" --runs \
  "$LAB/results/client-guard-hold-nocopy-1" "$LAB/results/client-guard-nocopy-gpu-1" \
  "$LAB/results/client-guard-nocopy-repair-gpu-1" "$LAB/results/client-guard-nocopy-reject-gpu-1" \
  "$LAB/results/client-guard-nocopy-repair-gpu-late-1" "$LAB/results/client-guard-nocopy-repair-gpu-late-2" \
  --out "$LAB/results/client-guard-audit-new.json"
xcrun clang++ -arch x86_64 -std=c++17 -O2 -fobjc-arc "$EXP/test_client_block.mm" \
  "$LAB/results/client-guard-build-new/libClientCallback.dylib" -framework Foundation \
  -o "$LAB/results/client-guard-contract-test-new"
"$LAB/results/client-guard-contract-test-new"
```

The 2026-10-28 cohort used application SHA-256 `e7ffa4d1a358fe1b2fda390a8e6bdb6d3413998252ba3660bea7307c4244c944`, observer `7d1685e71dca35efcbc23cf9c8fef4ff38316eccf4cf9580da74ef9295bcbbd6`, and client library `142b75390115d354b1b4a0ac66f7df49c0dbd68c3e4fabae14908d373705ca19`. The auditor checks frozen build sources, signed artifacts, dependency paths, host manifests, client-block provenance and retention, GPU outputs and controls. A fresh build requires separate GPU qualification. The public archive contains no proprietary driver binaries or captured GPU programs.
