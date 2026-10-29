# Public-Metal point-transform client with process-local opt-in

A separately linked test program uses public Metal calls to load the shader,
create a pipeline and queue, create a CPU-encoded indirect command buffer,
bind two buffers and execute point draws. It does not link or call KeplerMetal
symbols. An explicitly loaded, signed process-local bootstrap checks the exact
client executable, GPU, local carrier, shader library and manifest hashes. It
adapts objects in that process and maps the tested public pipeline descriptor to
the previously [certified transform profile](VERTEX_POINT_TRANSFORM.md). It
enables queue-local render encoder adaptation; no system-wide class, framework
or driver is replaced.

The scope is a purpose-built client with a pinned shader, descriptor, NVIDIA
stack and counts 0–256. The executable hash is a local selection guard, not a
signature authority or proof that arbitrary runtime behavior is safe. The
bootstrap does not qualify third-party or hardened applications, other library
loading APIs, arbitrary descriptors, shaders or GPU-generated commands. It
requires explicit process-local `DYLD_INSERT_LIBRARIES` opt-in. The client must
still ensure the two distinct buffers do not alias and must synchronize CPU/GPU
access. No performance claim is made.

## Validation

Two unmodified client processes using direct Metal and two using the ICB path
with opt-in produced identical raw results for counts 0, 1, 17, 128 and 256.
The [audit](standalone-point-transform-validation.json) checks 10,240 raw
input/output values against a CPU oracle, 5,120 guard bytes and eight copied
draw packets. Two non-injected ICB controls stopped at the missing internal
`newIndirectCommandBufferWithDescriptor:maxCount:options:` selector before GPU
dispatch. Four further controls refused a changed client, changed manifest,
different valid shader library, and altered pipeline descriptor. For the last
two, the native factory was used and the resulting unregistered pipeline was
refused before command execution. `nm -u` confirmed that the test client has no
undefined KeplerMetal symbols. All ten tested processes were signed, terminal
and nonoverlapping under the cooperative reservation. Only the explicitly
checked system components were verified unchanged.

Earlier exploratory processes are retained locally: two opt-in attempts
stopped before drawing because the default vertex descriptor was non-nil, and
an initial wrong-library test caused the native pipeline validator to abort that
single process because the library lacked the requested function. Its lease was
terminal; the final wrong-library control uses a valid differently compiled
shader and is refused without that assertion. These exploratory processes are
not counted in the ten-process audit.

A subsequent [library-loading experiment](STANDALONE_POINT_LOADERS.md) covers
URL and data routes for a related client. This does not demonstrate transparent compatibility for existing applications
or an installed driver update. The direct and adapted output equality does not
measure performance. The runtime archive SHA-256 is
`9c5edae4c0bf28878d2a808e117c21472a455ff5236048f88f2f9ed9b3ad22e3`.

## Reproduce

Build the exact transform shader and runtime using [the earlier instructions](VERTEX_POINT_TRANSFORM.md).
The carrier is obtained locally and is not redistributed. A second, valid
shader with a changed constant is used only for the rejection control. These
hashes depend on the qualified toolchain. Run from the repository root with
fresh paths; never retry a process whose terminal state is unknown.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
LEGACY='/path/to/render_state_carrier.metallib'
SHADER='/path/to/transform.metallib'
A='/absolute/path/to/built-runtime-archive'
E=bridge/experiments/standalone_point_transform
S="$R/standalone-wrong-shader-new"
mkdir "$S"
python3 - "$S/wrong.metal" <<'PY'
from pathlib import Path
import sys
s=Path('bridge/experiments/vertex_point_transform/transform.metal').read_text()
assert s.count('3u + 7u')==1
Path(sys.argv[1]).write_text(s.replace('3u + 7u','3u + 9u'))
PY
xcrun -sdk macosx metal -std=macos-metal2.0 -c "$S/wrong.metal" -o "$S/wrong.air"
xcrun -sdk macosx metallib "$S/wrong.air" -o "$S/wrong.metallib"
B="$R/standalone-point-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --shader "$SHADER" --wrong-shader "$S/wrong.metallib" --manifest "$PWD/bridge/experiments/vertex_point_transform/profiles.json" --out "$B"
for n in 1 2; do for mode in direct native auto; do python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$R/standalone-point-$mode-$n-new"; done; done
for mode in wrong-client wrong-manifest wrong-library bad-descriptor; do python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$R/standalone-point-$mode-new"; done
python3 "$E/audit.py" --build "$B" --archive "$A" --runs "$R/standalone-point-direct-1-new" "$R/standalone-point-native-1-new" "$R/standalone-point-auto-1-new" "$R/standalone-point-direct-2-new" "$R/standalone-point-native-2-new" "$R/standalone-point-auto-2-new" "$R/standalone-point-wrong-client-new" "$R/standalone-point-wrong-manifest-new" "$R/standalone-point-wrong-library-new" "$R/standalone-point-bad-descriptor-new" --out "$R/standalone-point-audit-new.json"
```
