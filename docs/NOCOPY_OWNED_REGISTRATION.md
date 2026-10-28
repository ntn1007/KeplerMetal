# Owned callback state for scoped Metal work registration

This prototype extends the [Metal work registrar](NOCOPY_METAL_REGISTRATION.md). The registrar and its installed completion blocks now hold a `std::shared_ptr` to the registry gate, instead of a raw pointer whose lifetime had to be maintained externally. A command buffer's retained completion block keeps that gate alive until the block itself is released. The completion sink and its captures retain their own independent lifetime obligations.

On the pinned GTX 880M profile, six signed hosts ran without overlapping GPU reservations. Five registered two Metal command buffers apiece on separate queues and destroyed the registrar before submission; both handlers still ran, and an independent CPU oracle verified 40,960 GPU result words. Three guarded hosts called the client block once after both commands completed, their results were checked and the selected native root release returned. Each client deallocation succeeded and a VM region query no longer covered its own 4 KiB allocation. The native GPU, rejected-policy and retained-buffer controls made no client call. Two late duplicate guard calls were **simulated by the test** and rejected. The raw-evidence audit rejects 61 altered records.

In the GTX host another shared owner deliberately keeps the gate alive while it observes root and validates results. A separate CPU-only mock test drops both the caller's shared owner and the registrar with a completion pending, verifies the gate is still alive, delivers the simulated completion, releases the retained handler and verifies the gate is destroyed. The mock tests also cover nil, committed, duplicate, late and failed work, registration exceptions and 16 concurrent registrations. The same source hashes pass ThreadSanitizer on an M1 Max. Those mock and sanitizer tests do not execute a Kepler GPU command.

This remains an opt-in laboratory prototype, not a transparent driver fix or application SDK. The client must register every relevant uncommitted command and serialize each registration with its submission. The registry cannot find omitted or foreign work. An abandoned uncommitted command can retain its handler and leave the gate waiting; no timeout is evidence that the GPU is safe. The sink must safely own any state it captures and must not introduce retain cycles. The tested VM unmapping is not a generic deallocator contract, and successful user-space release does not prove kernel resource destruction. The unmodified native control did not deliver the block in the observed window; a lab action invokes it. No video or performance improvement is claimed. No system component is modified.

## Reproduce on the pinned profile

Obtain dependencies as described in [Dependencies](DEPENDENCIES.md), verify the current GTX `nvAccelerator` registry ID and use the cooperative GPU reservation. Each process owns its allocation. Use fresh paths and run serially:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified current nvAccelerator registry ID>'
EXP=bridge/experiments/nocopy_gpu_owned_registration
python3 "$EXP/experiment.py" build --out "$LAB/results/owned-registration-build-new"
for item in hold-nocopy:1 nocopy-gpu:1 nocopy-repair-gpu:1 nocopy-reject-gpu:1 nocopy-repair-gpu-late:1 nocopy-repair-gpu-late:2; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/owned-registration-build-new" \
    --out "$LAB/results/owned-registration-$mode-$n" --lab "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/owned-registration-build-new" --runs \
  "$LAB/results/owned-registration-hold-nocopy-1" "$LAB/results/owned-registration-nocopy-gpu-1" \
  "$LAB/results/owned-registration-nocopy-repair-gpu-1" "$LAB/results/owned-registration-nocopy-reject-gpu-1" \
  "$LAB/results/owned-registration-nocopy-repair-gpu-late-1" "$LAB/results/owned-registration-nocopy-repair-gpu-late-2" \
  --out "$LAB/results/owned-registration-audit-new.json"
xcrun clang++ -std=c++17 -O2 -fobjc-arc -pthread "$EXP/test_metal_registration.mm" \
  -framework Foundation -framework Metal -o "$LAB/results/owned-registration-mock-test-new"
"$LAB/results/owned-registration-mock-test-new"
```

The 2026-10-28 cohort used application SHA-256 `06f767cbe353498d3892fb7204b2dc07f3becd926b4d2021a0ea285801f0eef3`, observer `7ddbb0b218da7d3949409a87a2f638992daaf1ed12d80485b2ef1fb687263a64`, and client library `4d26427c85743dc3a83b6e994fc5fffc33d6b1f60d27cf8f06062df5ed6d12ff`. The registrar header SHA-256 was `f7ed6bc7c7c2083b1b14c303a41ddec2f67601240b143ccaa2f7e0fba06f5e6e`, concurrency header `4edd98cc17ba1ffa7317e5c06701a46a3246d3ca0f31a8a8625d67f1248679f9`, and mock test `c00d886e48c185b4fef9809ddeed2f79b21de8c4d2a30a8e80e4f4c7a479e0f1`. The auditor checks frozen sources, signed artifacts, manifests, registrar release, registration refusals, completion counts, client retention, GPU outputs and controls. A fresh build requires separate GPU qualification.
