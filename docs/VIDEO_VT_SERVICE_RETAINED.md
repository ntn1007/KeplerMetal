# VideoToolbox searches the retained NVIDIA service

In two instrumented hardware-required H.264 requests, the test client selects
the unique `nvAccelerator` whose PCI ancestor is NVIDIA `10de:1198`, retains
its public IOKit service right and verifies its registry ID before session
creation. While that right remains held, the name passed to Metal's pinned
registry-ID lookup and the name passed to the VideoToolbox `IOGVACodec` search
both match the retained name in the same process. The lookup uses `IOService`,
options `1`, and returns null at the following call site. Both requests return
`-12906` and no frames.

Keeping the right alive prevents a freed name from being reused during this
comparison. The retained service may affect its lifetime relative to an
ordinary application; it is released on client exit. The client uses public
IOKit calls and does not change the registry. The loaded Metal and VideoToolbox
regions, known string layout and relevant call bindings are checked at witness
arming; bindings are not rechecked at each call. The property lookup's key is
recognized through a bounded constant-string read, not an independent CF type
query at the call. Debugging can change timing. This confirms the service
relationship in the tested process, not a hardware decoder or the sole reason
for the error.

The outcome is consistent with the older [direct observer](VIDEO_DEPENDENCIES.md),
which also reported an absent `IOGVACodec` on the NVIDIA service. Its separate
process-local presence substitution advanced selection but did not decode.
The later [AppleGVA comparison](VIDEO_GVA_HISTORICAL_CLASSIFICATION.md) found a
second renderer-classification obstacle. Neither result supplies a legitimate
NVIDIA codec value or establishes a compatible downstream provider.

Twenty-two CPU cases include mismatched queried and retained names, wrong
registry identity, wrong key and the filter branch controls. Two observed and
two plain software processes decode 24 frames matching 2,764,800 reference
bytes. The four hardware requests fail with no frames. All eight processes
terminate under separate nonoverlapping cooperative GPU reservations. The
[audit](video-vt-service-retained-validation.json) checks the retained-client
result, same-process comparisons, code and calibration hashes, receipts and
software pixels. [Offline mutations](video-vt-service-retained-mutations.json)
challenge the evidence without GPU work. An earlier non-retaining exploratory
cohort also terminated; it is not included in the qualified counts. Three
system files were hashed around each run; MetalOld and display inventory were
checked during audit. No system component, OCLP or firmware was modified.

## Reproduction

Use the fixture/reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
pinned cache and common cooperative lab reservation, with fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_service_retained
C="$LAB/results/vt-service-retained-cal-new"
B="$LAB/results/vt-service-retained-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-service-retained-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-service-retained-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-service-retained-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-service-retained-mutations-new"
```

Next, investigate the later decoder-selection and renderer-classification
barriers already identified by the scoped counterfactuals. This is not a
driver fix.
