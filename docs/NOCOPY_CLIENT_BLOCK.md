# Separately supplied Metal no-copy block

This research prototype extends the [separately compiled client callback experiment](NOCOPY_CLIENT_CALLBACK.md). The client dynamic library now **creates the Metal-compatible block itself**; the laboratory host passes this block directly to `newBufferWithBytesNoCopy`. The host verifies the observed driver object holds the same block, and resolves the block's invoke function to the separately signed client library. When the gated laboratory action explicitly invokes it, the client block frees the test allocation.

On the pinned GTX 880M profile, six signed hosts ran without overlapping GPU reservations. Five hosts each submitted two GPU commands on separate queues; an independent oracle checked 40,960 output words. Three guarded hosts invoked the client block once after both commands completed, their output was verified and the observed root deallocation call returned. Mach VM deallocation succeeded and the region probe no longer covered the test allocation. The held-buffer, native GPU, and rejected-policy controls made no client release. Two late duplicate calls were **simulated by the test** and rejected. The raw-result audit rejects 52 deliberately altered records. A separate CPU-only contract test checks unauthorized and wrong-pointer refusals, one successful release and duplicate rejection.

This is a process-local, cooperative proof involving a specially written block, one owned 4 KiB allocation, shared test-state pointers, a narrow native profile and two explicitly tracked commands. The host's gate and observer are not an implementation for arbitrary Metal blocks or unknown queues. Successful user-space deallocation does not prove kernel resource destruction or system-wide lifetime safety. The native driver did not itself deliver the tested callback during the observed window; the controlled action invoked it. No performance, video or ordinary-application support is claimed, and no system component is changed.

## Reproduce on the pinned profile

Obtain dependencies as described in [Dependencies](DEPENDENCIES.md), verify the current GTX `nvAccelerator` registry ID and use the common cooperative GPU reservation. Each test process owns its own allocation. Run serially and use fresh paths:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified current nvAccelerator registry ID>'
EXP=bridge/experiments/nocopy_gpu_client_block
python3 "$EXP/experiment.py" build --out "$LAB/results/client-block-build-new"
for item in hold-nocopy:1 nocopy-gpu:1 nocopy-repair-gpu:1 nocopy-reject-gpu:1 nocopy-repair-gpu-late:1 nocopy-repair-gpu-late:2; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/client-block-build-new" \
    --out "$LAB/results/client-block-$mode-$n" --lab "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/client-block-build-new" --runs \
  "$LAB/results/client-block-hold-nocopy-1" "$LAB/results/client-block-nocopy-gpu-1" \
  "$LAB/results/client-block-nocopy-repair-gpu-1" "$LAB/results/client-block-nocopy-reject-gpu-1" \
  "$LAB/results/client-block-nocopy-repair-gpu-late-1" "$LAB/results/client-block-nocopy-repair-gpu-late-2" \
  --out "$LAB/results/client-block-audit-new.json"
xcrun clang++ -arch x86_64 -std=c++17 -O2 -fobjc-arc "$EXP/test_client_block.mm" \
  "$LAB/results/client-block-build-new/libClientCallback.dylib" -framework Foundation \
  -o "$LAB/results/client-block-contract-test-new"
"$LAB/results/client-block-contract-test-new"
```

The 2026-10-28 cohort used application SHA-256 `b6b0d6b1c0759c26d98d7037e6b28635e26ec85806168ca048bc922e91889c7b`, observer `b01f9e91c61c75e6e7bd4f7550135eb13b9bb396bf82b21fa68a6a0628779430`, and client library `34ff02a48c561b9091adcaebbc7a04fed38ace83b63c5a9651f35e769cb16ba0`. The auditor checks the immutable GPU build sources, signed artifacts, dependency paths, host manifests, results, block location, client counts and controls. A fresh build requires separate GPU qualification. The public archive contains source rather than proprietary driver binaries or captured GPU programs.
