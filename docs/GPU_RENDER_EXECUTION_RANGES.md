# GPU-controlled render execution ranges

The later [GPU draw-record qualification](GPU_RENDER_COMMAND_RECORDS.md) adds
scalar draw arguments and closes the nonempty release-before-commit boundary.
The results below remain the preceding range-only cohort.

The scoped render adapter now implements the ordinary
`executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:` selector for
its **own CPU-encoded render ICBs**. A native NVIDIA-compiled compute kernel
produces the execution range on the GTX 880M. A second native compute pass
materializes per-slot native indirect draw arguments. Native direct/indexed
indirect-draw APIs consume those arguments without a CPU range readback.

This extends branch B, Metal command support. It does not replace the installed
driver, implement Apple's native ICB binary ABI, generate arbitrary render
commands on the GPU, or make unmodified applications compatible. Integration
remains level 2: an application explicitly installs and prepares the scope.

## Contract

1. Install the existing render scope and register the existing certified native
   render pipelines and resource profiles. Register the exact source-built
   `indirect_render_range.metal` library with
   `enableGPUIndirectRenderRangesWithLibraryData:expectedSHA256:error:`.
2. Encode the range producer on a retained command buffer belonging to the
   scope's queue. Its range is two `uint32_t` words, location then length,
   in a same-device buffer at a four-byte-aligned offset.
3. Call `prepareIndirectRenderCommands:indirectBuffer:indirectBufferOffset:commandBuffer:error:`
   **before opening the render encoder**, after the producer. This snapshots
   the owned CPU commands and encodes the native materializer.
4. On that same recording command buffer, open the scoped render encoder and
   invoke the ordinary indirect-range selector with the exact ICB/range/offset.
   Consume each preparation once. Do not mutate its ICB or range between
   preparation and consumption. CPU command copying does not copy preparation.
5. Reprepare the ICB only after its previous command buffer completes
   successfully. A failed GPU completion poisons that preparation. Discard a
   command buffer after an encoding failure requiring discard; do not submit
   partially encoded work as a successful operation.

The existing maximum is 16 slots. Empty slots have zero draw counts. Invalid
or overflowing ranges become an empty execution in this adapter; this is an
explicit conservative policy, not a claim about Apple's unspecified invalid
input behavior. All command snapshots are validated even when their eventual
GPU range excludes them. Native pipeline/profile, geometry/index-domain,
fragment certification, render-target and command-buffer ownership checks
remain required. Pipeline and touched vertex/fragment bindings, including
inline bytes, are restored before the following caller draw. Viewport and
scissor are inherited without rewriting them.

The plan retains its native library, compute pipeline, initializer buffers,
draw records and resources through completion. It accepts no CPU-supplied
draw-argument buffer. The range, arguments and witnesses are read by the CPU
only **after GPU completion in the diagnostic client**. Production execution
does not require these readbacks. The current implementation still encodes
one native indirect draw per occupied CPU slot, including zero-count draws;
it does not demonstrate a CPU encoding-cost reduction.

## Qualification on the GTX 880M

Ten fresh signed processes cover eight scenarios each: full range, interior
window, prefix, suffix, empty, out-of-bounds, integer overflow, and a skipped
producer whose initialized range stays empty. The default path combines a
direct draw, indexed UInt16 and UInt32 draws with positive/negative base
vertices and nonzero base instances, plus an empty slot. Separate modes
cover the historical inherited pipeline and combined fragment texture/sampler
argument buffers uploaded to private GPU memory. A following marker draw
checks caller pipeline/vertex/fragment restoration; alternate trials use
inline parameters and a restrictive scissor.

- 983,040 raster float channels match the independent CPU oracle; maximum
  observed error is zero. All 57,984 explicitly counted raster/argument/witness
  guard bytes pass. Input buffers and sampled textures are also checked in full.
- 48 complete candidate/reference raster files are byte-identical. The native
  references receive a CPU-resolved range explicitly; candidates do not.
- 70 producer dispatches and 56 range-materializer dispatches are encoded.
  The no-consumer control still materializes arguments but produces no ICB
  geometry. Empty/invalid/skipped-producer cases retain only the caller marker.
- Two lifetime modes reuse the same ICB across eight successful generations,
  then restore classes and release the scope, commands and source resources
  before the final commit. Their complete readbacks still match. This last
  generation has an empty ICB range: the materializer and caller marker still
  execute, but this alone does not prove a nonempty fragment draw after release.
- The contracts mode checks eleven refusals on each of two trials, including
  pending reuse, alignment/length, queue/retention, wrong kernel pin,
  mismatched range, a copied ICB without preparation, command mutation/reset
  and duplicate consumption.

The complete seven-object archive is
`4244e0fb173d97c9eee4609aef177620822dff44e66e5ada0bbf3ad27ac094a0`.
Only `KeplerCPUICB.o` and `KeplerNativeRenderDraws.o` differ from the preceding
`875cb4b9f3e30022b110709b0bd9c7fe6c0efcb58ddc19eccedbec6543c52551`
archive. The remaining five objects are byte-identical. The new native
materializer library pin is
`97ead5c886a747a189d48674ca6b6a4647d23282331c00660008577705a33974`.
An exported-source rebuild produces seven byte-identical runtime objects and
eight identical archive-member payloads, including the symbol index. The
complete `ar` hash changes because its member timestamp and group-ID fields
differ; the hash above identifies the GPU-tested local archive, not a
metadata-independent archive hash. The materializer rebuilds from public MSL
with the recorded Xcode Metal toolchain. Neither
library nor any proprietary binary is distributed.

The qualified environment is macOS 26.7.1/build 25G241, SDK 26.2, Apple clang
17.0.0/clang-1700.6.4.2 and Metal 32023.864/metalfe-32023.864, on x86_64
GK104/SM30. Installed GeForceMTLDriver SHA-256 is
`e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645`.
The private encoder-owner layout remains an exact-profile dependency.

## Reproduction

Use fresh output directories and the common host reservation. `KP_WORK`
is an existing experiment directory and `KP_LAB` the existing shared lab root.
Builds never submit GPU work; runs acquire the shared lease, copy/sign an
immutable executable and verify its terminal state.

```sh
python3 tools/build_from_source.py --out build/render-ranges-local
python3 bridge/tools/public_indirect_render_ranges.py build \
  --library build/render-ranges-local --out "$KP_WORK/client"
python3 bridge/tools/public_indirect_render_ranges.py run \
  --build "$KP_WORK/client" --out "$KP_WORK/gpu" --mode gpu \
  --reservation-root "$KP_LAB"
python3 bridge/tools/public_indirect_render_ranges.py run \
  --build "$KP_WORK/client" --out "$KP_WORK/native" --mode native \
  --reservation-root "$KP_LAB"
```

Also run `no_consumer`, `contracts`, `lifetime`, `fragment`, `fragment_native`,
`fragment_lifetime`, `legacy`, `legacy_native` serially. Stop at any failure
and inspect that exact process/lease before another host. The builder freezes
all 47 runtime source pins, the seven-object manifest, client sources,
independent oracle, runner, shader assets and executable hashes. It validates
the oracle syntax before compiling the client. The portable corruption tests
submit nothing to Metal:

```sh
python3 -m unittest discover -s tests -p test_indirect_render_ranges.py -v
```

`audit_indirect_render_ranges.py` recomputes the full new cohort and the
current-archive compute/adapter regression, including raw comparisons to the
preceding texture cohort. Its `--help` documents the required local evidence
directories; historical asset prerequisites for the FP64/CAS reception remain
described in [ADAPTER_PROFILES.md](ADAPTER_PROFILES.md).

## Limits and next work

The qualification covers the registered profiles, four-slot test ICBs,
tracked private resources, one queue and one recording thread. Other slot
capacities, untracked-resource synchronization, concurrent mutation,
in-flight re-preparation, arbitrary shaders and a failed-device recovery path
remain unqualified. The application must supply correct producer/resource
dependencies and use the explicit prepass. Encoding within an already open
render pass is not supported by this extension.

No performance benchmark, general Metal 3/4 conformance, driver installation,
Linux-driver port or transparent application integration is claimed. The next
useful checks are a nonempty release-before-commit fragment draw and GPU
generation of render command contents with its resource contract, followed by an application reception using the supported public
calls. The complete modernized macOS driver goal remains open.
