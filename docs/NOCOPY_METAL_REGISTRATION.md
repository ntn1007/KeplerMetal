# Automatic completion callbacks for explicitly registered Metal work

This prototype extends the [explicit work registry](NOCOPY_WORK_REGISTRY.md). An adapted client gives an uncommitted Metal command buffer to a local registrar. The registrar allocates its work token and attaches the Metal completion handler itself; the client no longer manually reports that command buffer's completion. Registration is closed before submission in the tested host. Duplicate buffers, registration after closure and buffers already enqueued are refused.

On the pinned GTX 880M profile, six signed hosts ran without overlapping GPU reservations. Five hosts each registered and submitted two Metal command buffers on different queues; their completion callbacks arrived through the registrar, and an independent CPU oracle checked 40,960 GPU result words. Three guarded hosts called the independent client block once after both completions, output validation and the observed root release and return. Each client deallocation succeeded and the VM region query no longer covered its test allocation. A native GPU control, rejected-policy control and retained-buffer control made no client call. Two late duplicate guard calls were **simulated by the test** and rejected. The raw-evidence audit rejects 60 deliberately altered records.

A CPU-only mock test covers nil, already committed, duplicate and late buffers, two successful completions, duplicate completion, a failed completion and an exception while adding a handler. Sixteen concurrent registrations are exercised with independent mocks; the same source hashes also pass ThreadSanitizer on an M1 Max. The mocks do not execute Metal commands and the sanitizer result does not validate the Kepler GPU.

## Contract and limits

This is an opt-in lab prototype, not a transparent driver fix or application-facing SDK. The client must register **every** relevant command buffer before committing it and serialize each buffer's registration against its submission. The registrar cannot detect omitted buffers, foreign queues or resource use outside the declared set. The C++ gate and captured completion sink must outlive all registered callbacks; the tested host uses process-lifetime state. An abandoned, uncommitted registered buffer leaves the gate waiting. A failed completion or registration exception prevents delivery. The caller must retain ownership on refusal; no automatic recovery is implied.

The host additionally requires CPU output validation and a pinned private observation of the selected root release. The client block unmaps its own test-only 4 KiB Mach VM allocation; this postcondition is not a generic deallocator contract. The native driver did not call the block in the observed unmodified control: a laboratory action invokes the guard. User-space deallocation does not prove kernel resource destruction. Unknown client callbacks, untracked work, video and performance are not qualified. No system component is modified.

## Reproduce on the pinned profile

Obtain dependencies as described in [Dependencies](DEPENDENCIES.md), verify the current GTX `nvAccelerator` registry ID and use the cooperative GPU reservation. Each process owns its allocation. Use fresh paths and run serially:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified current nvAccelerator registry ID>'
EXP=bridge/experiments/nocopy_gpu_metal_registration
python3 "$EXP/experiment.py" build --out "$LAB/results/metal-registration-build-new"
for item in hold-nocopy:1 nocopy-gpu:1 nocopy-repair-gpu:1 nocopy-reject-gpu:1 nocopy-repair-gpu-late:1 nocopy-repair-gpu-late:2; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/metal-registration-build-new" \
    --out "$LAB/results/metal-registration-$mode-$n" --lab "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/metal-registration-build-new" --runs \
  "$LAB/results/metal-registration-hold-nocopy-1" "$LAB/results/metal-registration-nocopy-gpu-1" \
  "$LAB/results/metal-registration-nocopy-repair-gpu-1" "$LAB/results/metal-registration-nocopy-reject-gpu-1" \
  "$LAB/results/metal-registration-nocopy-repair-gpu-late-1" "$LAB/results/metal-registration-nocopy-repair-gpu-late-2" \
  --out "$LAB/results/metal-registration-audit-new.json"
xcrun clang++ -std=c++17 -O2 -fobjc-arc -pthread "$EXP/test_metal_registration.mm" \
  -framework Foundation -framework Metal -o "$LAB/results/metal-registration-mock-test-new"
"$LAB/results/metal-registration-mock-test-new"
```

The 2026-10-28 cohort used application SHA-256 `c4b3d76b7d01e0e06c246062af0d7fdf5736396d4aaef191e563b9f85d0b0f8e`, observer `d2c4eebcaf9451196fffdbce432e31657b3f14a43be324967b932be79504c617`, and client library `0b24d04f48f03308282339f8fe077dbc6fcf6acc5eae06d5046c730fb3685a63`. The registrar source SHA-256 was `246460c64e274c302d94da3ce98cff37c37c000c3c9bf30e799ca3103f9d4c9b`, concurrency header `4edd98cc17ba1ffa7317e5c06701a46a3246d3ca0f31a8a8625d67f1248679f9`, and mock test `b5afe6af899b607d67311893d36ec5aa49179ca7a14f036f0715d4f857c28cae`. The auditor checks frozen sources, signed artifacts, dependency paths, manifests, registration refusals, completion counts, client retention, GPU outputs and controls. A fresh build requires separate GPU qualification.
