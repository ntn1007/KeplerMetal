# Apple CPU ICB sample: concrete integration gaps

The actual [Apple CPU ICB sample](https://developer.apple.com/documentation/metal/encoding-indirect-command-buffers-on-the-cpu)
was downloaded from the official [archive](https://docs-assets.developer.apple.com/published/2af775e98586/EncodingIndirectCommandBuffersOnTheCPU.zip)
into the local lab, not added to this repository. The examined archive SHA-256
is `559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311`;
its license and source remain in that archive. The original macOS Debug target
built successfully with signing disabled in an isolated derived-data folder.
The app was not launched.

The current source defines **15 objects**, although the documentation text
describes 16. Its controller checks `supportsFamily:MTLGPUFamilyMac2`; two
local GTX observations report Mac 1 true and Mac 2 false. The check is a
software compatibility gate, not proof that all associated hardware features
are absent. This project does not spoof the family result.

The sample encodes 15 non-indexed draws with an inherited pipeline, three
explicit vertex buffers and varying `baseInstance`. Its shader reads per-vertex
data and per-object parameters through explicit device pointers and a frame
state through a constant pointer. Each frame blits CPU-updated data into a
private buffer before rendering. It also uses a drawable and depth attachment.
Those requirements are distinct from the previously qualified two-buffer
stage-in client.

## Measured on the GTX, without dispatch

Two signed, nonoverlapping processes created a native pipeline from the actual
Apple shader and inspected its reflection. The reflected active, read-only
vertex buffer arguments are:

| Index | Name | Reflected data size | Alignment |
|---|---|---:|---:|
| 0 | `vertices` | 16 bytes | 4 bytes |
| 1 | `object_params` | 8 bytes | 4 bytes |
| 2 | `frame_state` | 8 bytes | 256 bytes |

These are reflection values, not complete dynamic buffer bounds. The sample
indexes vertices by vertex ID and object parameters by instance ID; safe
support must derive bounds from actual draw geometry and shader semantics.
Registration of this shader with an empty stage-in layout was refused with
`Fragment resources or non-stage-in vertex ABI are not supported`. A
three-buffer inherited descriptor was also refused by the scoped adapter in
this state. Both refusals happened before submission; there were **zero GPU
dispatches**. The actual Apple app, its shader's output and its private-buffer
frame ordering have not been tested. The [auditor](apple-cpu-icb-gap-validation.json)
checks hashes, process termination, reflection, refusals and a bounded set of
unchanged system-file hashes.

The [subsequent native reference](APPLE_EXPLICIT_NATIVE.md) executes the sample
shader on the GTX with shared and private frame buffers and base instances 0/1.
The later [scoped ICB profile](APPLE_EXPLICIT_ICB.md) qualifies those cases for
the exact shader with explicit bounds. A bounded multi-command test and
application-local integration remain to be assessed. These steps do not imply
Mac 2 conformance or transparent driver replacement.

## Reproduce

The profile deliberately uses an empty stage-in layout to expose the current
registration refusal. The local archive must match the pinned digest; do not
copy Apple sources or compiled vendor binaries into the publication repository.
Use fresh outputs and establish terminal process state before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
mkdir "$S"
curl -fsSL 'https://docs-assets.developer.apple.com/published/2af775e98586/EncodingIndirectCommandBuffersOnTheCPU.zip' -o "$S/AppleSample.zip"
printf '%s  %s\n' '559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311' "$S/AppleSample.zip" | shasum -a 256 -c || exit 1
unzip -q "$S/AppleSample.zip" -d "$S/source"
xcodebuild -project "$S/source/Indirect Command Buffers on CPU.xcodeproj" -scheme 'macOS - Indirect Command Buffers on CPU' -configuration Debug -derivedDataPath "$S/derived" CODE_SIGNING_ALLOWED=NO build > "$S/build.log" 2>&1
xcrun -sdk macosx metal -std=macos-metal2.0 -I "$S/source/Renderer" -c "$S/source/Renderer/AAPLShaders.metal" -o "$S/apple.air"
xcrun -sdk macosx metallib "$S/apple.air" -o "$S/apple.metallib"
python3 - "$S" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]);h=hashlib.sha256((p/'apple.metallib').read_bytes()).hexdigest()
x={'schema':1,'library_SHA256':h,'pipelines':[{'name':'apple-cpu-icb','vertex':'vertexShader','fragment':'fragmentShader','attributes':[],'layouts':[]}]}
(p/'apple-empty-stage-manifest.json').write_text(json.dumps(x,indent=2)+'\n')
PY
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-gap-new
A="$PWD/build/apple-gap-new"
E=bridge/experiments/apple_cpu_icb_gap
B="$LAB/results/apple-gap-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$S/apple-empty-stage-manifest.json" --out "$B"
for n in 1 2; do
  python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode direct --out "$LAB/results/apple-gap-$n-new"
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-gap-1-new" "$LAB/results/apple-gap-2-new" --out "$LAB/results/apple-gap-audit-new.json"
```

The pinned metallib and manifest hashes depend on the qualified toolchain;
the builder refuses a different output rather than silently repinning it.
