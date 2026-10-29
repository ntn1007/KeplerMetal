# VideoToolbox searches for `IOGVACodec`

Two instrumented hardware-required H.264 requests pass the GTX-linked
availability dictionary to the local VideoToolbox filter. At its property
search call, the request argument is the same pointer received by the filter.
A bounded read recognizes the checked constant-string layout and ASCII bytes
`IOGVACodec`; the service argument is nonzero, the plane is `IOService`, and
options are `1`. The following call-site return value is null. The filter then
returns zero. This is a property lookup observation, not proof that the video
engine executed or that this condition alone causes the public `-12906` error.

The loaded filter bytes, string shape and call sites are pinned. The relevant
loaded slots resolve to `FigCFDictionaryGetInt64IfPresent` and
`IORegistryEntrySearchCFProperty` when the witness is armed; they are not
rechecked at the actual calls. The request decoding is restricted to a small
allowlist; unrecognized layouts and names are reported as unknown/other.
The nonzero service's registry identity and the detailed reason for the null
return are not established by this test. Debugging can alter timing.

An earlier [AppleGVA observation](VIDEO_GVA_PROPERTY_NODE_LINK.md) independently
found `IOGVACodec` absent in its own observed `nvAccelerator` query. That query
used different call context and options; the present witness does not prove
that the two service objects are identical. A separate earlier fabricated-value
counterfactual did not establish hardware decoding. No NVIDIA value is inferred
or installed here.

Twenty CPU cases cover a known property, a different property and an
unrecognized object, along with the prior filter branches. Their initial
verification expected a parent image name that the CPU unwinder did not
resolve. A corrected verifier copied the unchanged completed logs and signed
host to a fresh directory, rechecked their hashes and signature, and accepted
them without re-execution. Filter-frame checks remain separate. The video
audit still requires the actual parent image and offset.

Two observed and two plain hardware requests returned `-12906` with zero
frames. Two observed and two plain software controls produced 24 frames
matching 2,764,800 reference bytes. All eight processes terminated under
nonoverlapping cooperative GPU reservations. The [audit](video-vt-property-identity-validation.json)
checks source and calibration hashes, bindings at arm, event order and software
output. [Offline mutations](video-vt-property-identity-mutations.json) challenge
the evidence without GPU work. Three system files were hashed around each run;
MetalOld and display inventory were checked during audit. No system component,
OCLP or firmware was changed.

## Reproduction

Use the fixture/reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
pinned cache and common cooperative lab reservation, with fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_property_identity
C="$LAB/results/vt-property-cal-new"
B="$LAB/results/vt-property-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-property-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-property-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-property-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-property-mutations-new"
```

Next, establish the queried service's identity and compare its properties
with the separate AppleGVA observation. This is not a driver fix.
