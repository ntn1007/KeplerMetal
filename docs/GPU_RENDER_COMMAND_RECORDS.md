# GPU-generated render draw arguments

The scoped render adapter now accepts scalar draw records generated on the
GTX 880M. This extends the preceding [GPU execution-range route](GPU_RENDER_EXECUTION_RANGES.md):
the GPU supplies draw counts and geometry start positions, rather than only
selecting a range of CPU-fixed draws. A native compute materializer validates
each record against a host-certified geometry envelope, then emits the native
indirect arguments consumed by the existing render transport.

This is branch B, Metal command support, at integration level 2. The CPU still
chooses the pipeline, buffers, textures, samplers, primitive topology and index
format of each slot. These resources remain sealed; records contain no GPU
addresses or resource handles. This is not Apple's native ICB representation,
an implementation of the native MSL `render_command` type, transparent support
for unmodified applications, or a new system driver.

## Wire contract and validation

[`KeplerRenderCommandRecords.h`](../bridge/src/KeplerRenderCommandRecords.h)
defines a 32-byte record: magic, kind, five argument words and one reserved word.
Kind 0 means direct drawing, 1 UInt16 indexed drawing, and 2 UInt32 indexed
drawing. Argument order follows the native direct/indexed indirect-draw
structures; the unused fifth direct word must stay zero. Reserved must be zero.

The CPU-certified ICB command defines the maximum draw/instance counts, allowed
vertex or index window, base vertex/instance, pipeline and resource bindings.
The GPU materializer permits subranges inside that envelope. It checks subtraction
bounds without an overflowing endpoint addition, requires the original kind and
base values, and limits the instance count. A bad magic/reserved word, mismatched
kind, out-of-envelope count/start/base/instance or empty CPU slot produces a
zero-count native draw. Invalid execution ranges also suppress all draws.

Witness reason codes are 0 accepted, 1 magic/reserved mismatch, 2 kind mismatch,
3 argument bounds/base mismatch, 4 empty CPU slot. Witnesses are diagnostics,
not a CPU prerequisite to execution. The source records and materialized
arguments are read back only after completion by the qualification client.

The materializer is rebuilt from public native MSL and pinned to:

```
8d0c21cfb3b16ad646ab13f143dbbac091cd28e8b9cb791e21cb443fb1500ee7
```

Registration requires that exact immutable library snapshot, the named entry
point, thread width 32, and the complete six-buffer reflection contract.
Registration itself submits no GPU work. The runtime checks device, queue,
retained command-buffer ownership, record/range offset alignment and extent,
the original CPU command snapshots and the render-pass profile before encoding.
It accepts no caller-supplied native draw-argument allocation.

## Application use

1. Install the existing render scope and register its certified pipelines and
   resource profiles. Encode each CPU ICB slot with its maximum approved draw.
2. Register the new materializer through
   `enableGPURenderCommandRecordsWithLibraryData:expectedSHA256:error:`.
3. On a retained command buffer belonging to the scope's queue, encode the GPU
   producer of scalar records and of the two-word execution range.
4. Before opening the render pass, call the new overload:

```objc
[scope prepareIndirectRenderCommands:icb
                     commandRecords:gpuRecords
               commandRecordsOffset:recordOffset
                     indirectBuffer:gpuRange
               indirectBufferOffset:rangeOffset
                      commandBuffer:commandBuffer
                              error:&error];
```

5. Open the scoped render encoder on that same command buffer and use the
   public `executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:` selector.

The preceding single-consumption, immutable-snapshot, completion/reuse and
discard-on-encoding-failure rules still apply. The application supplies proper
producer/resource synchronization; the qualification uses tracked private
resources. Do not mutate the ICB, range or records between preparation and
consumption. Native pipeline/resource binding and caller-state restoration
remain the existing transport's responsibility. No CPU decision based on GPU
record readback occurs on the candidate path.

## GTX qualification

Ten new signed processes cover six eight-frame record modes plus four nonempty
release-before-commit probes. The record producer chooses either triangle of
each rectangle from private GPU input data. The independently checked results
include native direct references, UInt16/UInt32 indexing, positive/negative base
vertices, nonzero base instances, empty slots, scissor, textures/samplers and
private fragment argument tables. Safe malformed scalar inputs exercise bad
magic, wrong kind, oversized count/start, wrong base vertex and excess instances;
the checked materializer suppresses them before native draw consumption.
Skipped-producer and skipped-consumer controls remain explicit.

- 638,976 new float channels match the independent CPU raster/sampling oracle,
  with zero observed error; 37,568 counted raster/argument/witness guard bytes
  are intact. Source buffers and sampled textures are checked in full.
- The full reception also reruns the preceding ten range modes on the new
  archive and the compute/FP64/CAS/render regression. The machine-readable
  [validation summary](gpu-render-record-validation.json) records exact counts,
  raw comparisons, terminal processes and archive identity.
- Four nonempty release probes drain the encoding call's autorelease pool,
  observe destruction of both the scope and the software ICB through weak
  references, then commit the retained native command buffer. The fragment
  cases observe the texture and sampler still alive before commit and produce
  the correct textured triangles. This closes the empty-range limitation of
  the preceding release experiment.

The complete seven-object GPU-tested archive is:

```
ed87b2bd10f20ace7f743ca6525fe92f0a66f8fd13ff11a33fe659ae6a3c480f
```

Only `KeplerCPUICB.o` differs from the preceding `4244e0fb…` archive; the other
six objects are byte-identical. Runtime sources number 48. Archive container
timestamps/group IDs may change on rebuild; compare the seven object hashes
and archive-member payloads separately from the timestamped `ar` file hash.
No compiled shader, driver or archive is distributed.

Environment: GTX 880M/GK104/SM30, x86_64 macOS 26.7.1/build 25G241, SDK 26.2,
Apple clang 17.0.0/clang-1700.6.4.2 and Metal 32023.864/metalfe-32023.864.
The installed driver remains the exact `e240d54a…` profile described in
[DRIVER_PROFILES.md](DRIVER_PROFILES.md); no system component or OCLP changes.

## Reproduction

`KP_WORK` is a new experiment location and `KP_LAB` the existing shared host
reservation root. Every host runs from an immutable signed copy under that
reservation; serialize launches and stop on any failure before inspecting its
exact terminal state. Builds submit no GPU work.

```sh
python3 tools/build_from_source.py --out build/render-records-local
python3 bridge/tools/public_indirect_render_ranges.py build \
  --library build/render-records-local --out "$KP_WORK/client"
python3 bridge/tools/public_indirect_render_ranges.py run \
  --build "$KP_WORK/client" --out "$KP_WORK/records" --mode records \
  --reservation-root "$KP_LAB"
```

Repeat serially with `records_native`, `fragment_records`,
`fragment_records_native`, `records_no_consumer`, `records_no_producer`,
`release`, `fragment_release`, `records_release`, `fragment_records_release`,
then the preceding ten range modes. Use fresh output directories. The shared
builder freezes the runtime manifest/sources, client, oracle, native shader
assets and signed runner inputs. Recompute the complete reception with
`bridge/tools/audit_gpu_render_records.py --help`; its references are the
preceding range and texture evidence directories. Historical FP64/CAS asset
prerequisites remain separate and are described in [ADAPTER_PROFILES.md](ADAPTER_PROFILES.md).

Portable corruption tests submit no malformed GPU program or native stream:

```sh
python3 -m unittest discover -s tests -p test_indirect_render_ranges.py -v
```

## Remaining boundaries

No GPU-selected pipeline/resource binding or arbitrary command generation is
implemented here. The tested clients use four slots, one queue, tracked private
resources, one instance and the registered triangle profiles. Other capacities,
concurrent writers, valid zero-count/other geometry combinations, untracked
synchronization, all invalid-record corner cases and GPU-error recovery remain
unqualified. A custom shader is still responsible for staying within its own
allocated output buffers; validating scalar records does not sandbox arbitrary
GPU programs.

There is no performance benchmark or speedup claim. The CPU still encodes one
native indirect draw per occupied slot, including suppressed draws. The next
command-support boundary is GPU selection among certified pipeline/resource
states and a source-level render-command interface, followed by an application
reception. General Metal 3/4 support, system-driver modernization and transparent
integration remain distinct unfinished objectives.
