# Explicit four- and five-vertex geometry contracts

A registered, nonlegacy stage-in render pipeline can now declare an exact
non-indexed triangle count of four or five in its `direct_geometry` manifest.
Previously, the adapter accepted these draws without an explicit geometry
contract but rejected the same count during registration when a contract was
present. The registration predicate now agrees with the existing draw predicate;
execution still requires the declared start, count, instance count and base
instance to match exactly. Resource bounds and the other existing checks remain
in place. Counts with other unsupported remainders remain refused.

The tested profile uses a pinned read-only stage-in shader, start 1, one
instance, base instance 0 and counts 4 or 5. These are opt-in,
application-local ICBs, not transparent system-wide Metal support. This change
does not enable writable vertex buffers or imply a performance gain.

## Validation

The previous runtime refused registration of the supplied four-vertex contract
before rendering, with `Direct geometry contract invalid`. On the updated
runtime, two direct/adapted GTX process pairs completed eight render buffers.
The offline auditor checked 98,304 float channels, 4,096 guard bytes, equality
of direct/adapted images, and the 4/5 counts in the adapted native packets.
Four negative controls requested counts 3 or 5 against the declared count-4
contract; each was refused before the command buffer was submitted. The GPU
runs were signed, terminal and serialized under the cooperative reservation.

The previous noncontracted profile was also requalified on the same runtime in
four additional GTX processes: 12 render buffers, 147,456 checked float
channels, 6,144 guard bytes, and ten expected refusal controls. Captured packet
counts and pixels do not prove individual trailing vertex invocations. Earlier
unrelated GPU cohorts were not rerun. The checked system components were
unchanged; this is not an inventory of every system file.

[Contract audit](render-trailing-geometry-validation.json) and
[noncontracted regression](render-trailing-geometry-regression.json) contain
hashes and scope. The runtime archive SHA-256 is
`d6b6d017c920f5deccf6b6f7e5392a7709be4e423bedb6e473cab1a1b5abcb4a`.

## Reproduce

Provide the local, hash-pinned NVIDIA/Apple carrier assets; they are not
included in this project. Use fresh output directories and do not retry a GPU
process until it is known to be terminal. The final auditor also requires the
recorded previous build and refusal; those records are not recreated by the
commands below.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
LEGACY='/path/to/render_state_carrier.metallib'
VERTEX='/path/to/vertex_io_carrier.metallib'
OLD_BUILD='/path/to/recorded-previous-build'
OLD_AUTO='/path/to/recorded-previous-refusal'
E=bridge/experiments/render_trailing_geometry
python3 tools/build_from_source.py --out build/geometry-new
A="$PWD/build/geometry-new"
B="$LAB/results/geometry-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --legacy "$LEGACY" --vertex "$VERTEX" --manifest "$PWD/$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/geometry-$mode-$n-new"
  done
done
python3 "$E/audit.py" --build "$B" --archive "$A" --baseline-build "$OLD_BUILD" --baseline-auto "$OLD_AUTO" --runs "$LAB/results/geometry-direct-1-new" "$LAB/results/geometry-auto-1-new" "$LAB/results/geometry-direct-2-new" "$LAB/results/geometry-auto-2-new" --out "$LAB/results/geometry-audit-new.json"
```
