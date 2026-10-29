# Public Metal library-loading routes for the point transform

The process-local point-transform bootstrap now recognizes the exact certified
shader when the public-Metal client loads its library by file path, file URL,
`dispatch_data_t`, or a `dispatch_data_t` formed by concatenating two segments.
For approved bytes, it creates the library from an immutable certified snapshot
and tags its function before matching the bounded pipeline descriptor. Other
libraries are forwarded to the native factory; they are not mapped to the
certified pipeline. File, URL and data callbacks call the native data factory
through its original class, avoiding recursive interception in these tested
paths.

The client imports no KeplerMetal symbols. This remains an explicitly injected,
process-local experiment using one purpose-built executable, one shader,
manifest, descriptor and pinned NVIDIA stack. A local client hash is a selection
guard, not an independent authorization boundary. It does not qualify
third-party or hardened applications, arbitrary shaders, library layouts,
concurrent calls, non-file URLs or global transparent Metal support. The caller
must preserve the existing [two-buffer profile](VERTEX_POINT_TRANSFORM.md)
constraints, including non-aliasing and CPU/GPU synchronization. No performance
claim is made.

## GTX evidence

The [audit](standalone-point-loaders-validation.json) verifies 27 signed,
terminal, nonoverlapping processes under the shared lab reservation:

- Eight direct and eight opt-in runs: two of each for each loading route. The
  auditor checked 40,960 input/output words against a CPU oracle, 20,480 guard
  bytes and 32 adapted command packets. All raw results matched. For the
  segmented route, the client reported two regions from `dispatch_data_apply`.
- Four native ICB controls, one per route, each stopped at the missing internal
  ICB selector before drawing.
- Four valid but different shader-library controls, one per route, were passed
  to the native factory; their unregistered pipelines were refused before
  execution. Changed-client, changed-manifest and altered-descriptor controls
  also stopped before execution.

`nm -u` verified that the signed client has no undefined KeplerMetal symbols.
The checked system components were unchanged; this is not a complete inventory
of every system file. The runtime archive SHA-256 is
`9c5edae4c0bf28878d2a808e117c21472a455ff5236048f88f2f9ed9b3ad22e3`.

## Reproduce

Use the exact locally built runtime, transform and valid wrong-shader fixture
from [the previous standalone experiment](STANDALONE_POINT_TRANSFORM.md). The
legacy carrier is obtained locally and not distributed. The hashes depend on
the qualified toolchain. Use fresh output paths; inspect any process whose
terminal state is unknown before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
LEGACY='/path/to/render_state_carrier.metallib'
SHADER='/path/to/transform.metallib'
WRONG='/path/to/wrong.metallib'
A='/absolute/path/to/built-runtime-archive'
E=bridge/experiments/standalone_point_loaders
B="$R/point-loaders-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --shader "$SHADER" --wrong-shader "$WRONG" --manifest "$PWD/bridge/experiments/vertex_point_transform/profiles.json" --out "$B"
for route in file url data segmented; do
  for n in 1 2; do
    for mode in direct auto; do
      python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --route "$route" --out "$R/point-loaders-$mode-$route-$n-new"
    done
  done
  for mode in native wrong-library; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --route "$route" --out "$R/point-loaders-$mode-$route-new"
  done
done
for mode in wrong-client wrong-manifest bad-descriptor; do
  python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --route file --out "$R/point-loaders-$mode-new"
done
python3 "$E/audit.py" --build "$B" --archive "$A" --runs \
  "$R"/point-loaders-{direct,auto}-{file,url,data,segmented}-{1,2}-new \
  "$R"/point-loaders-{native,wrong-library}-{file,url,data,segmented}-new \
  "$R"/point-loaders-{wrong-client,wrong-manifest,bad-descriptor}-new \
  --out "$R/point-loaders-audit-new.json"
```

The auditor groups runs by their recorded mode and route; the argument order is
not a claim about execution order. The runner checks actual process timestamps
and the cooperative reservation for overlap.
