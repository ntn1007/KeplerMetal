# Typed fragment-buffer transition

An explicitly adapted application can translate a pinned Metal shader's
`render_command.set_fragment_buffer` operation and use it to select one of two
previously certified fragment argument buffers. The GPU producer changes a
render-state record, and the existing native materializer renders a texture
using the selected buffer. The texture, sampler and nested parameter buffers
are genuine Metal resources. The producer does not dereference the supplied
fragment pointer; it matches it to a retained resource and a permitted
state-transition row. The target application must register the producer and
render profiles, retain resources and declare indirect dependencies.

This is an opt-in, process-local fragment-only context. It does not yet combine
with the indexed/vertex/pipeline context in [TRIPLE_RENDER.md](TRIPLE_RENDER.md),
implement the native Apple ICB ABI, change the installed driver, support
unmodified applications, establish Metal 3/4 conformance or demonstrate a
performance gain. State tables are bounded and validated against their exact
owned context and retained objects; they are not a sandbox for arbitrary GPU
pointers. The current fragment planner requires 256-byte-aligned offsets and
GPU addresses and rejects unsupported or ambiguous transitions.

The public Metal shader in `bridge/src/air_fragment_binding.metal` tests the
SDK-typed operation. Its AIR signature has a fragment pointer and slot but no
vertex-stride argument. The exact-profile lowering preserves entry dataflow and
replaces only supported command operations. A certified native NVIDIA backend
then compiles the lowered program; no NAK substitution is used. A signed,
construction-only capture and offline disassembly check the exact driver,
program and absence of unresolved native calls before the execution tests.

Two certified states differ only in the fragment argument buffer. Each contains
a real texture, sampler and parameter buffer. One gives RGBA `(0.25, 0.5,
0.75, 1)` and the other `(0.125, 0.25, 0.375, 1)`. The independent CPU oracle
checks all pixels and the unchanged input texture, the GPU records, transition
rows, witness, buffer guards, receipts, signed executable and frozen inputs.
Direct native draw images are compared byte for byte; controls cover no
dispatch, disabled setter, reversed selection, foreign buffer, absent extension,
invalid extension magic and an argument-root alias refusal. The native
references deliberately draw nothing for the three invalid cases.

On October 27, 2026, the audited cohort covered 30 fragment cases and seven
same-runtime triple/pipeline regressions in serialized signed hosts. It checked
368,640 image channels and 368,640 input-texture channels, with zero CPU error;
14 native-image pairs and 15 repeated-image pairs matched exactly. Both alias
refusals passed. The source-only export passed 361 CPU tests, rebuilt the
producer and host byte-identically, and passed two more GPU hosts. All 39 final
hosts ran without overlap. [Audit summary and fingerprints](fragment-binding-validation.json).

## Reproduction

Use the supported macOS/SDK/driver profile, fresh output directories, a
separately obtained `envydis`, and the shared GPU reservation. Run exactly one
Metal host at a time. A timeout is not proof that a host has finished.

```sh
python3 tools/build_from_source.py --out build/fragment-runtime
python3 bridge/tools/public_air_fragment_binding.py build --out /absolute/producer
python3 bridge/tools/public_air_fragment_binding.py inspect --build /absolute/producer \
  --out /absolute/inspection --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_fragment_binding.py certify --run /absolute/inspection \
  --envydis /absolute/envytools/envydis
python3 bridge/tools/public_fragment_binding_render.py build \
  --library "$PWD/build/fragment-runtime" --producer /absolute/producer \
  --inspection /absolute/inspection --out /absolute/client-build
python3 bridge/tools/public_fragment_binding_render.py run --build /absolute/client-build \
  --out /absolute/results/cohort-01-gpu --mode gpu \
  --reservation-root /absolute/common-lab/bridge
```

The complete mode list, two cohort names and same-runtime regression builders
are documented in `bridge/tools/audit_fragment_binding_render.py`. Each run
contains a frozen independent oracle and terminal reservation receipt. Recheck
all runs with `audit_fragment_binding_render.py ROOT --out /absolute/audit.json`.
