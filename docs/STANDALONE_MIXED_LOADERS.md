# Public Metal loading routes for the standalone mixed application

The process-local bootstrap for the [standalone mixed compute/render application](STANDALONE_MIXED_APPLICATION.md) now recognizes its two qualified libraries through public Metal loading by file path, file URL, `dispatch_data_t`, and concatenated two-segment `dispatch_data_t`. Each library is checked against its own exact certified snapshot before its named functions can be matched to the registered compute or render pipeline. A different library is passed to the native loader and its unregistered pipeline is refused by the scoped indirect path. Calls to the native data loader use the original device superclass, avoiding recursive interception in these tested routes.

The client creates its own device, queue, libraries and pipelines, encodes a compute ICB and an indexed render ICB in one command buffer, and reads results only after completion. The compute shader writes the private index buffer read by the render shader. The executable imports no KeplerMetal symbols; the bootstrap is explicitly injected into **this one hash-pinned process**. This is a purpose-built application and a fixed pair of shaders, not unmodified third-party app support, native Apple ICB compatibility or transparent system integration. Snapshot hashes are selection guards, not an independent authorization boundary. Non-file URLs, arbitrary data layouts, shaders, pipeline descriptors and concurrent calls remain unqualified.

## GTX evidence

Thirty-nine signed, terminal processes ran sequentially under the cooperative laboratory GPU reservation:

- Four direct controls cover each loading route without injection; sixteen injected cases cover every compute/render route pair, plus four diagonal repeats.
- Four more injected cases omit the producer or the render consumer for file and segmented data. The independent CPU oracle checks **344,064 float channels** across all 28 output processes, along with pixel guards, index buffer, atomic counter and buffer guards. All direct and complete indirect outputs match; missing-producer and missing-render outputs are blank as expected.
- Eight valid but different shader libraries, four for each pipeline domain, are forwarded to the native loader and subsequently refused as unregistered. Modified-client and modified-manifest controls are refused before scope installation. A changed color-write descriptor is forwarded and then refused. The wrong-library and descriptor controls execute an initial GPU blit before the main sequence is refused; they are not no-GPU-work tests.

For the segmented input the application observed two regions via `dispatch_data_apply`; the adapter maps and checks the combined bytes. The [sanitized audit](standalone-mixed-loaders-validation.json) checks signatures and frozen inputs, native/injected logs, the 16-pair coverage, output pixels and guards, scoped ICB execution and restoration records, terminal processes and nonoverlapping cooperative reservations. The test ties the device registry ID to the separately verified PCI `10de:1198` in [PUBLIC_MIXED_CLIENT.md](PUBLIC_MIXED_CLIENT.md). The auditor records the current runner source hash, but cannot independently prove the runner source hash for each already completed process; signed app/bootstrap hashes, outputs and process receipts are checked. The reservation does not exclude WindowServer or other nonparticipating software. No installed driver, framework or OCLP file was modified.

The test does not prove full Metal ICB support, hardware video decoding, visible presentation or a speed gain. It does not qualify an app outside this exact profile. It extends the earlier [point-transform loader test](STANDALONE_POINT_LOADERS.md) to a single application containing both compute and render libraries and their GPU dependency.

The later [bundle-default extension](STANDALONE_MIXED_BUNDLES.md) tests the main application and an additional bundle.

## Reproduction

Use the matching SDK/driver profile, the pinned compute/render metallibs and a common laboratory reservation. Build outputs and run directories must be fresh. Resolve any unknown process state before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/standalone_mixed_loaders
python3 tools/build_from_source.py --out build/mixed-loaders-new
A="$PWD/build/mixed-loaders-new"
B="$LAB/results/mixed-loaders-build-new"
python3 "$E/experiment.py" build --library "$A" \
  --compute /path/to/cpu_icb_gpu_indices.metallib \
  --render /path/to/render_state_carrier.metallib --out "$B"
runs=()
for route in file url data segmented; do
  out="$LAB/results/loaders-direct-$route-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode direct --compute-route "$route" --render-route "$route" || exit 1
  runs+=("$out")
done
for c in file url data segmented; do for r in file url data segmented; do
  out="$LAB/results/loaders-auto-$c-$r-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode auto --compute-route "$c" --render-route "$r" || exit 1
  runs+=("$out")
done; done
for route in file url data segmented; do
  out="$LAB/results/loaders-repeat-$route-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode auto --compute-route "$route" --render-route "$route" || exit 1
  runs+=("$out")
done
for route in file segmented; do for mode in no-producer no-render; do
  out="$LAB/results/loaders-$mode-$route-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" --compute-route "$route" --render-route "$route" || exit 1
  runs+=("$out")
done; done
for mode in wrong-compute wrong-render; do for route in file url data segmented; do
  out="$LAB/results/loaders-$mode-$route-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" --compute-route "$route" --render-route "$route" || exit 1
  runs+=("$out")
done; done
for mode in wrong-client wrong-manifest bad-descriptor; do
  out="$LAB/results/loaders-$mode-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" --compute-route file --render-route file || exit 1
  runs+=("$out")
done
python3 "$E/audit.py" --library "$A" --build "$B" --prior docs/public-mixed-client-validation.json --runs "${runs[@]}" --out "$LAB/results/loaders-audit-new.json"
```

The prior receipt contains a boot-specific registry ID. A different boot requires a newly qualified identity rather than silently changing the receipt. Project source for the two deliberately different negative-control shaders is built locally; proprietary libraries and GPU binaries are never distributed.
