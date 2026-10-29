# Standalone public Metal compute and render application

A separately compiled and signed executable creates its own Metal device, queue, libraries, functions and compute/render pipeline states through public API calls. It encodes a compute operation that writes private GPU indices followed by an indexed render operation in the same command buffer. The application contains no KeplerMetal calls or headers. An explicitly injected, process-local bootstrap matches this exact executable and shader snapshots, installs the existing scope, maps the two approved pipeline requests to its registered pipeline objects and enables automatic queue factories. The executable uses an indirect command buffer for each operation; no CPU reads the indices between compute and render.

This is a purpose-built test application, **not an unmodified third-party app or transparent system integration**. The bootstrap relies on explicit `DYLD_INSERT_LIBRARIES`, one approved executable, one queue, two exact libraries, one manifest, specific function names and a bounded render descriptor. Its hashes are selection guards, not an independent security boundary. Unrecognized pipeline descriptors go through the native factory and are refused by the scoped indirect command path if their pipeline is not registered. No system framework, driver, WindowServer or OCLP component is modified.

## Evidence

Eight signed, serialized GTX processes cover two each of native-direct, injected indirect, no-producer and no-render modes. The native-direct app runs without injection. An independent auditor checks 98,304 float channels, guard bytes, index values and the GPU atomic counter. Direct and indirect images, indices and counters match across both pairs. The active compute path counts 32 invocations; with the producer absent the counter and initial indices remain unchanged, and with rendering absent the image remains blank. The application reports the same GTX registry identity as the earlier [public mixed-client test](PUBLIC_MIXED_CLIENT.md), which resolved PCI `10de:1198`.

Three additional processes verify rejection of a different signed executable, a modified manifest and a render descriptor with a different color-write mask. The first two are refused before scope installation. The bad-descriptor case performs an initial GPU blit, then the native fallback pipeline is refused by the scope before the user's indirect compute/render sequence; it is not a no-GPU-work test. The [sanitized audit](standalone-mixed-validation.json) checks signatures, frozen client/bootstrap/workload and asset hashes, expected exit codes, eight CPU pixel oracles, the indirect execution and restoration events, and eleven terminal, nonoverlapping cooperative reservations. The reservation coordinates participating lab processes, not WindowServer or all other GPU users.

The two first exploratory injected runs fell back because the default vertex descriptor was a non-null object even when empty. They terminated before the main indirect sequence and are excluded. The final matcher accepts that object only when all inspected attributes and layouts have their default empty values. One earlier negative-control receipt incorrectly labeled its preceding initialization blit as no GPU work; that receipt is retained privately and excluded. The runner was corrected and the negative test repeated. The auditor records the current runner hash but cannot independently prove which runner source was used for each earlier process; it verifies the frozen executables, outputs and terminal receipts instead.

The qualified result is limited to this client and exact profiles. It does not prove complete ICB behavior, arbitrary libraries or descriptors, unmodified applications, visible presentation, general Metal 3/4 support, hardware video decode or improved performance. The bootstrap restores the scoped device and queue when the process exits; concurrent restoration and shared-class behavior outside this process were not qualified by this cohort.

The later [mixed-loader extension](STANDALONE_MIXED_LOADERS.md) qualifies additional public loading routes for both libraries.

## Reproduction

Use the matching SDK/driver profile, the pinned compute/render metallibs and the common laboratory GPU reservation. The build copies the project-owned workload source from `public_mixed_client`, verifies that the application has no project imports, signs it and then pins its signed hash into the separately signed bootstrap. Use fresh paths and serialize runs. If a process outcome is unknown, inspect that exact process and reservation before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/standalone_mixed_application
python3 tools/build_from_source.py --out build/standalone-mixed-new
A="$PWD/build/standalone-mixed-new"
B="$LAB/results/standalone-mixed-build-new"
python3 "$E/experiment.py" build --library "$A" \
  --compute /path/to/cpu_icb_gpu_indices.metallib \
  --render /path/to/render_state_carrier.metallib --out "$B"
runs=()
for n in 1 2; do
  for mode in direct auto no-producer no-render; do
    out="$LAB/results/standalone-mixed-$n-$mode-new"
    python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" || exit 1
    runs+=("$out")
  done
done
for mode in wrong-client wrong-manifest bad-descriptor; do
  out="$LAB/results/standalone-mixed-$mode-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" || exit 1
  runs+=("$out")
done
python3 "$E/audit.py" --library "$A" --build "$B" \
  --prior docs/public-mixed-client-validation.json --runs "${runs[@]}" \
  --out "$LAB/results/standalone-mixed-audit-new.json"
```

The prior receipt pins a boot-specific registry ID to tie this cohort to the separately verified PCI identity. A later boot may require a newly qualified prior identity rather than an undocumented repin.
