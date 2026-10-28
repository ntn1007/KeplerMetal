# Separately compiled no-copy client callback

This laboratory experiment extends the [scoped no-copy release witness](NOCOPY_RELEASE_WITNESS.md). A separately compiled, signed test-client dynamic library supplies a C callback through a function pointer captured by the Metal-compatible block. The client callback releases **only its registered, process-owned 4 KiB Mach VM allocation**. This establishes that the selected block can delegate to separately compiled client code; it is not a general implementation of application-provided Metal blocks.

On the pinned GTX 880M profile, six nonoverlapping signed hosts were audited. Five executed two Metal GPU commands each on two queues; an independent CPU oracle checked 40,960 output words. Three guarded hosts invoked the client callback exactly once after both commands completed and their results were checked, and after the observed root deallocation call returned. All three client calls returned Mach status zero; the region probe saw the owned allocation before and not after release. A native GPU control, a locally rejected policy, and a retained-buffer control made no client call. In two guarded cases the test itself made a synthetic late duplicate block call; the gate rejected both before reaching the client. The audit rejected 52 mutations of the recorded results and reservation state.

The callback library registers one exact pointer and length, checks its own call count, and exposes a status for the test; its ABI and guards are test-specific. The surrounding wrapper, ownership, completion list and driver profile are explicitly controlled. The process-local observation uses private implementation details and an ad hoc signature, with no modification to the installed driver or system. A successful release does not prove kernel resource destruction, safety for arbitrary work or callbacks, API compatibility for ordinary applications, or a performance improvement. The duplicate events were synthesized by the test, not observed native callbacks. No video execution was established.

## Reproduction on the pinned profile

Use locally obtained dependencies as described in [Dependencies](DEPENDENCIES.md), the current verified `nvAccelerator` registry ID and the cooperative lab GPU reservation. These commands build new binaries and release memory belonging to their own processes. Never substitute another allocation or skip the exact-profile checks.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified current nvAccelerator registry ID>'
EXP=bridge/experiments/nocopy_gpu_client_callback
python3 "$EXP/experiment.py" build --out "$LAB/results/client-callback-build-new"
for item in hold-nocopy:1 nocopy-gpu:1 nocopy-repair-gpu:1 nocopy-reject-gpu:1 nocopy-repair-gpu-late:1 nocopy-repair-gpu-late:2; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/client-callback-build-new" \
    --out "$LAB/results/client-callback-$mode-$n" --lab "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/client-callback-build-new" --runs \
  "$LAB/results/client-callback-hold-nocopy-1" "$LAB/results/client-callback-nocopy-gpu-1" \
  "$LAB/results/client-callback-nocopy-repair-gpu-1" "$LAB/results/client-callback-nocopy-reject-gpu-1" \
  "$LAB/results/client-callback-nocopy-repair-gpu-late-1" "$LAB/results/client-callback-nocopy-repair-gpu-late-2" \
  --out "$LAB/results/client-callback-audit-new.json"
xcrun clang++ -std=c++17 -O2 -pthread "$EXP/test_race_gate.cpp" -o "$LAB/results/client-race-test-new"
"$LAB/results/client-race-test-new"
xcrun clang++ -std=c++17 -O2 -pthread "$EXP/test_once_gate.cpp" -o "$LAB/results/client-once-test-new"
"$LAB/results/client-once-test-new"
```

The 2026-10-28 cohort used application SHA-256 `d1ec41c5654e5794f807713b6834fffb62c1d6309cf9cba4f4d87ddd9c8f32de`, observer `c0ad34c8e8dc6f09d02f528fd43a0d7511d19d4bf5bae1cc74d827c8b41f5aef`, and client library `0e8a46add987e324a6a32c85dc87448229591c7f3051f6985dd37fc01ce388b9`. The auditor checks frozen sources, signed binaries, dependency paths, host manifests, GPU values, client call counts and the negative controls. The source archive contains no proprietary driver, compiled binary or captured vendor GPU code. A fresh build requires its own separate qualification.
