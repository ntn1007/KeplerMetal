# Native vertex writes with rasterization disabled

A public-Metal direct-render probe runs a `void` vertex function with
`rasterizationEnabled = NO`. The function atomically ORs a bit for each vertex
ID from 0 to 4 into a shared buffer. It uses one buffer at index 0, no fragment
function and no KeplerMetal adapter. Each draw has a separate initialized
buffer and a completed command buffer. The client checks surrounding buffer
guards; the saved reports contain summarized masks and guard results, not raw
buffer snapshots. Native reflection reports an active read/write buffer on both
machines.

Two GTX 880M processes and two M1 Max reference processes produced these same
masks for each primitive and vertex count:

| Primitive | 0 | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| Point | `00` | `01` | `03` | `07` | `0f` | `1f` |
| Triangle | `00` | `00` | `00` | `07` | `07` | `07` |

For points, the visible writes demonstrate that this native path executes a
vertex shader with a writable buffer on the GTX for these cases. For triangles,
no write was visible for vertices that did not form a complete triangle. This
is not proof that those vertices were never invoked; repeated invocations and
suppressed writes cannot be distinguished by an OR mask. It is not a general
Metal guarantee or a test of indexed, indirect, instanced, concurrent or
adapter-driven draws. The shader restricts its write to IDs below five, and all
reported guard checks passed.

Apple documents that a [pipeline with rasterization disabled](https://developer.apple.com/documentation/metal/mtlrenderpipelinedescriptor/israsterizationenabled)
requires a `void` vertex function. The data above is empirical; Apple does not
thereby guarantee these exact triangle masks. The earlier
[rasterized non-void probe](TRAILING_VERTEX_INVOCATIONS.md) remains a separate
experiment and its compiler warning should not be attributed to this void
shader.

A later [adapter experiment](VERTEX_POINT_ADAPTER.md) supports one hash-certified
point-write shader and shared buffer; general writable vertex arguments and point
draws remain unqualified. Further extension must separately
qualify a matching pipeline, shader access and bounds, writable resource usage
and residency, buffer lifetime and GPU ordering, and command recording and
execution. Relaxing reflection alone would leave those obligations unmet. No
adapter or system driver changed in this experiment.

## Evidence and reproduction

The two signed GTX processes were terminal and nonoverlapping under the shared
reservation, and the system components checked by the runner were unchanged.
The M1 source was copied by SSH and its SHA-256 matched on both hosts; both
remote summaries were transferred back and verified against their observed
hashes. The M1 summaries are not independently signed remote execution
receipts. [Audit](vertex-void-write-validation.json). No performance benchmark
was performed.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/vertex_void_write
B="$LAB/results/vertex-void-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --out "$B"
for n in 1 2; do
  python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --out "$LAB/results/vertex-void-$n-new"
done
```

On a reference Mac, compile the same `client.mm` with `xcrun clang++ -O2
-std=c++17 -fobjc-arc client.mm -framework Foundation -framework Metal -o
application` and run it twice. The auditor accepts those result files and the
GTX build/run directories. It pins these historical M1 captures; new captures
need a reviewed profile. Do not retry an unknown GPU process before establishing
its terminal state.
