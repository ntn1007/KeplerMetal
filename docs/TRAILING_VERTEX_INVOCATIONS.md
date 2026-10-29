# Native vertex-write witness for incomplete trailing triangles

This independent **native direct-render** probe records a bit with a bounded
atomic OR from each vertex shader invocation. It compares counts 0, 3, 4 and 5
on the GTX 880M and on a MacBook M1 Max. It uses no KeplerMetal adapter or
private import. Each run creates its own pipeline and buffers; the shader
restricts its write index and position lookup to at most five vertices. Buffer
guards are checked by the client after command-buffer completion. The captured
reports contain summarized masks and guard results, not raw buffer snapshots.

| Requested vertices | GTX observed mask | M1 observed mask |
| --- | --- | --- |
| 0 | `0x00` | `0x00` |
| 3 | `0x07` | `0x07` |
| 4 | `0x07` | `0x07` |
| 5 | `0x07` | `0x07` |

The three low bits are positive controls for visible atomic writes from vertex
IDs 0–2. Neither bit 3 nor bit 4 appeared in these particular tests. This does
**not** establish whether trailing vertices were invoked but their writes were
suppressed, nor how many times any vertex was invoked. It does not establish a
Metal-wide guarantee, cover indexed or indirect draws, or validate arbitrary
shaders and render state. Repeating an atomic OR for one ID produces the same
mask. The offline Metal 2.0 compilation also emitted a warning about writable
resources in a non-void vertex function; this result should not be generalized
without establishing the contract for other workloads.

Native reflection reported one active read/write buffer at index 0 on both
machines. KeplerMetal's stage-in registration refuses arbitrary writable vertex
arguments. A later, distinct [certified point-write profile](VERTEX_POINT_ADAPTER.md)
does not make this witness an adapter test. The
previous [4/5-vertex adapter test](RENDER_TRAILING_VERTICES.md) used a different,
read-only shader; this witness must not be presented as testing that adapter.
Apple describes [render-stage resource usage](https://developer.apple.com/documentation/metal/mtlrendercommandencoder/useresource(_:usage:stages:))
and its [vertex-invocation statistic](https://developer.apple.com/documentation/metal/mtlcounterresultstatistic/vertexinvocations),
but neither source guarantees this specific observed mask.

## Evidence and reproduction

Two signed GTX processes ran sequentially under the cooperative lab GPU
reservation. Both command sequences completed, each reported intact guards,
and checked system components were unchanged. Two independent M1 processes
reported the same masks; the source was copied through SSH and its SHA-256 was
compared on both machines. The M1 result files were copied back and checked
against their remotely observed hashes. The M1 record is a summarized reference,
not an NVIDIA test or an independently signed remote execution receipt.
The [audit receipt](trailing-vertex-invocation-validation.json) records hashes,
counts and limitations. No performance benchmark was performed.

On the iMac, use fresh output directories and the established lab reservation:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/trailing_vertex_invocations
B="$LAB/results/vertex-witness-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --out "$B"
for n in 1 2; do
  python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --out "$LAB/results/vertex-witness-$n-new"
done
```

On a reference Mac, compile the same `client.mm` with `xcrun clang++ -O2
-std=c++17 -fobjc-arc client.mm -framework Foundation -framework Metal -o
application` and run it twice. The auditor accepts those two result files plus
the two iMac run directories and the build directory. It pins the historical
M1 summaries and source; new captures require a reviewed profile. A timed-out or
unknown GPU process must be inspected before any retry.
