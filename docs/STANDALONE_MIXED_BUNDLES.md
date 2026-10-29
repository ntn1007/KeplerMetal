# Default Metal libraries in an application and a bundle

The process-local mixed compute/render bootstrap now recognizes the exact certified compute library loaded by [`newDefaultLibrary`](https://developer.apple.com/documentation/metal/mtldevice/makedefaultlibrary%28%29?language=objc) from the app's main bundle, and the exact certified render library loaded by [`newDefaultLibraryWithBundle:error:`](https://developer.apple.com/documentation/metal/mtldevice/makedefaultlibrary%28bundle%3A%29?language=objc) from a separate bundle. The application creates its own public Metal device, queue, libraries and pipelines; compute and indexed render ICBs operate on the same private index buffer without an intermediate CPU read. Existing file loading remains available for either domain.

For these specific bundle layouts the bootstrap resolves `default.metallib` through `NSBundle`, compares its bytes with the separately certified immutable snapshot and creates the scoped library through the native data loader. Unknown snapshots are forwarded to the native default-library method. This is a pinned **process-local** experiment requiring explicit `DYLD_INSERT_LIBRARIES`, not transparent system integration or support for arbitrary apps, bundle layouts, locales, shader libraries or pipeline descriptors. Hashes select the exact profile; they are not an independent security boundary. The client imports no KeplerMetal symbols.

## GTX evidence

Twenty-five terminal processes ran sequentially under the cooperative GPU reservation:

- Sixteen output processes compare direct execution without injection against injected indirect execution, twice for each of the four compute/render route pairs: main-bundle default or file, crossed with separate-bundle default or file. All direct and complete indirect outputs match.
- Four more injected processes omit the compute producer or the render consumer. An independent CPU oracle checks **245,760 float channels** across the 20 output processes, plus pixel guards, the index buffer, atomic counter and buffer guards. The absent-producer case preserves the initialized indices; the absent-render case still counts 32 compute invocations and produces a blank image.
- Five refusal cases use a different valid compute library, a different valid render library, a changed render descriptor, a changed signed client or a changed manifest. The two identity controls are rejected before scope installation. The wrong-library and descriptor cases perform an initial GPU blit, then refuse the unregistered user compute/render sequence.

The [sanitized audit](standalone-mixed-bundles-validation.json) verifies the signed executable's hash, bootstrap signature, `Info.plist` and `default.metallib` hashes before and after each run, loader and scoped-execution events, restoration events, independently checked pixels and terminal nonoverlapping reservations. The client reports the same GTX registry identity as the separately PCI-verified [public mixed-client cohort](PUBLIC_MIXED_CLIENT.md). A registry ID is boot-specific. The reservation coordinates participating lab runners, not WindowServer or other GPU users. The auditor records the current runner source hash but cannot independently establish the runner source hash for each completed process.

The application bundle itself is **not signed as a unit**. The standalone executable is signed and verified before it is copied into the bundle; its embedded copy is checked byte-for-byte. A preliminary verification attempted on that executable while inside the unsigned bundle failed before launch and is excluded. The test does not qualify hardened-runtime or third-party applications, arbitrary bundle resolution, visible presentation, complete ICB behavior, Metal 3/4 conformance, hardware video or a performance improvement. No driver, framework or OCLP component was modified.

## Reproduction

Use the matching SDK/driver profile, pinned compute/render metallibs and a shared laboratory reservation. The runner creates fresh local application and resource bundles; they are laboratory artifacts, not a deployment package. All build and run paths must be new. Resolve an unknown child outcome before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/standalone_mixed_bundles
python3 tools/build_from_source.py --out build/mixed-bundles-new
A="$PWD/build/mixed-bundles-new"
B="$LAB/results/mixed-bundles-build-new"
python3 "$E/experiment.py" build --library "$A" \
  --compute /path/to/cpu_icb_gpu_indices.metallib \
  --render /path/to/render_state_carrier.metallib --out "$B"
runs=()
for n in 1 2; do for c in main file; do for r in bundle file; do for mode in direct auto; do
  out="$LAB/results/bundles-$n-$mode-$c-$r-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" --compute-route "$c" --render-route "$r" || exit 1
  runs+=("$out")
done; done; done; done
for n in 1 2; do for mode in no-producer no-render; do
  out="$LAB/results/bundles-$n-$mode-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" --compute-route main --render-route bundle || exit 1
  runs+=("$out")
done; done
for mode in wrong-compute wrong-render bad-descriptor wrong-client wrong-manifest; do
  out="$LAB/results/bundles-$mode-new"
  python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" --compute-route main --render-route bundle || exit 1
  runs+=("$out")
done
python3 "$E/audit.py" --library "$A" --build "$B" --prior docs/public-mixed-client-validation.json --runs "${runs[@]}" --out "$LAB/results/bundles-audit-new.json"
```

The prior receipt pins a boot-specific registry identity; another boot needs a newly qualified PCI identity rather than a silent repin. The locally built negative shaders are project source; proprietary libraries and GPU binaries are not distributed.
