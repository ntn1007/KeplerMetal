# Explicit GPU work registry for a scoped no-copy guard

This experiment extends the [independent client block guard](NOCOPY_CLIENT_GUARD.md) with a thread-safe registry of explicitly declared work. The test host registers each command buffer before submission, seals registration, records each completion status, verifies both outputs and observes the selected root release and its return. The controlled client block is eligible for delivery only when all those conditions are met and no recorded completion or validation failed.

On the pinned GTX 880M profile, six signed hosts ran without overlapping GPU reservations. Five hosts registered and submitted two Metal command buffers apiece on different queues, and the audit independently verified 40,960 GPU result words. In three guarded hosts, both completion handlers reported success before a single client callback freed its own 4 KiB Mach VM allocation. The native GPU control, rejected-policy control and retained-buffer control made no client call. Two late duplicate calls were **simulated by the test** and rejected. The raw-evidence audit rejects 58 deliberately altered records.

The CPU registry test covers registration sets of 1–32 tokens, duplicate and unknown completion tokens, failed work, refusal of late registration, and 500 five-thread interleavings. The same source hashes also pass ThreadSanitizer on an M1 Max; this checks the CPU synchronization implementation, not Kepler GPU execution.

The registry only knows work the client explicitly declares. It cannot detect unregistered Metal commands, buffers reused in another queue, unknown GPU clients or other uses of the allocation. It is a lab contract, not an automatic application-facing SDK or transparent driver fix. The test checks an allocation whose callback unmaps its own Mach VM region; this is not a generic deallocator contract. A successful user-space release does not prove kernel resource destruction. The native driver did not call the block during the observed unmodified control; a laboratory action initiated the guarded call. No video or performance improvement is claimed. No system components are modified.

## Reproduce on the pinned profile

Obtain dependencies as described in [Dependencies](DEPENDENCIES.md), verify the current GTX `nvAccelerator` registry ID and use the cooperative GPU reservation. Each process owns its allocation. Use fresh paths and run serially:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified current nvAccelerator registry ID>'
EXP=bridge/experiments/nocopy_gpu_work_registry
python3 "$EXP/experiment.py" build --out "$LAB/results/work-registry-build-new"
for item in hold-nocopy:1 nocopy-gpu:1 nocopy-repair-gpu:1 nocopy-reject-gpu:1 nocopy-repair-gpu-late:1 nocopy-repair-gpu-late:2; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/work-registry-build-new" \
    --out "$LAB/results/work-registry-$mode-$n" --lab "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/work-registry-build-new" --runs \
  "$LAB/results/work-registry-hold-nocopy-1" "$LAB/results/work-registry-nocopy-gpu-1" \
  "$LAB/results/work-registry-nocopy-repair-gpu-1" "$LAB/results/work-registry-nocopy-reject-gpu-1" \
  "$LAB/results/work-registry-nocopy-repair-gpu-late-1" "$LAB/results/work-registry-nocopy-repair-gpu-late-2" \
  --out "$LAB/results/work-registry-audit-new.json"
xcrun clang++ -std=c++17 -O2 -pthread "$EXP/test_race_gate.cpp" -o "$LAB/results/work-registry-cpu-test-new"
"$LAB/results/work-registry-cpu-test-new"
```

The 2026-10-28 cohort used application SHA-256 `a0121f8ef56a52a0f0a9520649a4de41493722decd5deb3f915a5730d24efbfd`, observer `5460fe0c7ee3c53ee248b03215f5a62443675670cdb7f6d779d2dd6411097da6`, and client library `daa4dc91ebe0ec5e1f0f4b1ca6adf027f6b1be9c9515b7e04763b4f71b4fc231`. The CPU concurrency header SHA-256 was `4edd98cc17ba1ffa7317e5c06701a46a3246d3ca0f31a8a8625d67f1248679f9` and test source `776d7a0dd0ea5c409294af78b0a6b8e5ab0fe8b81f628ab77f7641dff2ea57d9`. The auditor checks frozen sources, signed artifacts, dependency paths, run manifests, registered and completed work, client retention, GPU outputs and controls. A fresh build requires separate GPU qualification.
