# Scoped compute pipeline with native reflection

This experiment extends the pinned standalone compute-to-render ICB client to the public synchronous compute-pipeline factory with options and reflection. The bootstrap first invokes the native Metal factory for the tagged function and returns its actual reflection to the caller. Only the exact approved application, compute library, function and `ArgumentInfo | BufferTypeInfo` option pair can map to the already registered pipeline; the native and registered pipeline must have the same device, thread execution width, maximum threads and static threadgroup memory. An unrecognized option falls back to the native pipeline and the scoped ICB rejects that unregistered pipeline. The native factory's failure and errors are not replaced. A null reflection output pointer is also covered.

The reflection object belongs to the native pipeline produced for the same function and options, while the adapted call returns the registered pipeline. The listed property comparisons, pinned inputs and observed outputs do not establish general pipeline equivalence. This is a process-local experiment using explicit `DYLD_INSERT_LIBRARIES`, not a system driver change or support for arbitrary applications, shaders, options, reflection properties or full ICB semantics. The approved GPU function and render pipeline retain all prior bounds. Neither performance gains nor additional hardware functionality are claimed.

## Cohort and evidence

Twenty serial signed processes exercise native direct and injected indirect work twice each for the simple factory, reflection factory and null-reflection variant; four additional runs suppress either the producer or rendering. Four expected refusals cover an unapproved executable, altered manifest, render descriptor and compute options. The two latter controls perform the initialization GPU blit before their unregistered pipeline is rejected; neither executes the main indirect compute/render sequence.

The offline auditor independently checks each image and buffer against CPU expectations, guards, 32 invocations in active cases, direct/indirect byte identity, exact reflection arguments against the pinned manifest, device identity, logged scoped execution and restoration, signatures, build/source hashes, unchanged driver hashes and terminal nonoverlapping cooperative reservations. The cooperative reservation cannot exclude unrelated GPU clients. The runner source is copied into the build and checked on every run. The original cohort runner labeled `user_compute_render_executed` true for all positive modes, including the controls that suppress one stage. That field is too broad for those four controls; their actual behavior is verified from the mode, counter, indices and image. The frozen cohort runner is retained as `qualified_runner.py`; the reproduction runner now reports the flag only for the complete direct or indirect sequence. A separately signed repeat of the no-producer control verified that corrected label and the unchanged expected GPU outputs; it is not counted in the 20-process audited cohort. [Sanitized receipt](standalone-mixed-reflection-validation.json).

## Reproduction

Run on the matching iMac and driver profile with the pinned assets, a source-built runtime and the shared GPU reservation. The experiment signs an immutable executable, constrains injection to that process and refuses changed assets. Select fresh paths. Do not retry an unresolved GPU process until its exact state is known.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/standalone_mixed_reflection
python3 tools/build_from_source.py --out build/reflection-runtime-new
A="$PWD/build/reflection-runtime-new"
B="$LAB/results/reflection-build-new"
python3 "$E/experiment.py" build --library "$A" \
  --compute /path/to/cpu_icb_gpu_indices.metallib \
  --render /path/to/render_state_carrier.metallib --out "$B"
runs=()
for factory in plain reflection reflection-null; do
  for mode in direct auto; do
    for n in 1 2; do
      out="$LAB/results/reflection-$factory-$mode-$n-new"
      python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" --factory "$factory" || exit 1
      runs+=("$out")
    done
  done
done
for mode in no-producer no-render; do
  for n in 1 2; do
    out="$LAB/results/reflection-$mode-$n-new"
    python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" --factory reflection || exit 1
    runs+=("$out")
  done
done
for mode in wrong-client wrong-manifest bad-descriptor; do
  out="$LAB/results/reflection-$mode-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" --factory reflection || exit 1
  runs+=("$out")
done
out="$LAB/results/reflection-options-none-new"
python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode auto --factory options-none || exit 1
runs+=("$out")
python3 "$E/audit.py" --library "$A" --build "$B" \
  --prior docs/public-mixed-client-validation.json --runs "${runs[@]}" \
  --out "$LAB/results/reflection-audit-new.json"
```

The prior receipt carries a boot-specific registry ID. A different boot requires a newly qualified identity receipt, not an undocumented repin.
