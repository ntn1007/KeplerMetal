# Preserve typed shader dataflow during AIR reset lowering

A second unchanged SDK-typed shader now executes through AIR translation and
NVIDIA's native compiler on the GTX 880M. It combines indexed conditional reset
with ordinary buffer loads, uint32 arithmetic, branching, rotation and output
stores. This extends the compiler part of branch B; the caller still supplies
the explicit [project context](AIR_RENDER_RESET.md), rather than an Apple ICB.

## Mechanism

`air_reset_lowering.py` recognizes the bounded metadata graph for one eight-byte
command-buffer root at buffer zero. It follows the root/member/command nodes,
verifies their layout and binding, rejects shared or duplicate metadata and
other recognized command operations, then replaces only the command resource
description and reset intrinsic. Metadata numbers are not hardcoded. Ordinary
argument descriptors remain intact. The entry body must remain textually
identical except for the reset callee; all branches, arithmetic and stores stay.

This structural transformer is an offline compiler component, **not a GPU
qualification gate or a sandbox**. The builder separately pins the original
AIR and normalized IR before using its output. Unknown input hashes refuse.
Construction-only signed hosts capture the native programs, whose inspected
code must contain no decoded CALL or unknown instruction. Execution requires
the exact library/native-code/driver certificate and restored observer.
The unchanged helper, capture transport and section parser come from the
preceding [reset experiment](AIR_RENDER_RESET.md).

Two distinct entry bodies and renumbered metadata are covered by CPU tests.
The simple shader transformed by this new component reconstructs the exact
previously GPU-qualified library
`814ee95b88e7b7577ada32538d7c4e1d9a5de324781d9f7a7d824c4ae4bd2a97`.

## GPU reception

The original [`air_reset_dataflow.metal`](../bridge/src/air_reset_dataflow.metal)
is compiled normally with SDK headers, packed, extracted and translated. No
source-header substitution or native instruction patch is used. A separately
written MSL reference uses ordinary project buffer operations. An independent
Python oracle computes indices, branch decisions, uint32 results and reset
slots. The four-bit reversed index permutation gives one writer per valid slot
and exercises both branch paths. Indices beyond the 16-slot domain are ignored
by reset while their ordinary arithmetic results still appear.

| Final reception | Result |
| --- | --- |
| Signed terminal nonoverlapping hosts | 10: two inspections, two no-dispatch controls, six execution hosts |
| Compute dispatches | 96: 48 translated, 48 reference |
| Completed command buffers | 128 |
| CPU-checked readback | 245,760 bytes, including 49,152 guards; zero mismatches |
| Arithmetic output | 1,548 exact uint32 values |
| Reset records | 300: 150 translated, 150 reference |
| Identical candidate/reference files | 144 |
| Identical repeat / no-dispatch reference pairs | 192 / 48 |
| Portable CPU tests | 266, including 17 new tests |
| Inventoried system files | 87 unchanged |

Readback counts include guards, unchanged indices and sentinel regions, not
only shader-written data. Invalid context headers and null/misaligned record
addresses preserve records **while still producing the exact arithmetic
output**. Without dispatch, both outputs retain their sentinels. Empty work
also leaves them unchanged. Counts 0/1/7/16/37, capacities 1/7/16 and local
sizes 1/8/32/64 are tested. Invalid contexts use live, owned allocations; no
arbitrary pointer fuzzing is performed on the display GPU.

Each case observes four `Private` buffers: records/guards 1,152 bytes, witness
384, indices 384, context 32. Their requested total is 1,952 bytes; physical
VRAM occupancy is not measured. Upload and readback use normal Metal blits.
The translated/reference native programs have 1,280/1,344 bytes, respectively;
size is not a speed measurement. A separate successful 16-dispatch pilot is
excluded from the final statistics. Three CPU-only build iterations are kept;
only the final frozen host runs on the GPU.

Environment: macOS 26.7.1/build 25G241, SDK 26.2, Apple Metal 32023.864,
clang 17.0.0, GK104 PCI `10de:1198`. Exact hashes and source identities are in
[validation](air-reset-dataflow-validation.json) and
[source chain](air-reset-dataflow-source-chain.json).

## Reproduce

Use the [previous inspection/certification workflow](AIR_RENDER_RESET.md), with
`public_air_reset_dataflow.py` in place of `public_air_render_reset.py`.
Build into a fresh directory. Inspection outputs are named
`inspect-lowered` and `inspect-reference`. Run both variants sequentially in
`no_dispatch` mode under `cohort/no-dispatch/{lowered,reference}`, then in
`execute` mode under `cohort/execute-{0,1,2}/{lowered,reference}`. Each execution
uses its own variant's inspection certificate. The signed shared reservation
is mandatory, including inspections. Stop on any unresolved process or failure.

```sh
python3 bridge/tools/public_air_reset_dataflow.py build --out /absolute/fresh-build
# Inspect, certify and run as described above; use fresh output parents.
python3 bridge/tools/audit_air_reset_dataflow.py /absolute/session \
  --build /absolute/fresh-build --out /absolute/fresh-audit.json
python3 -m unittest discover -s tests -v
python3 tools/check_publication.py
```

No core runtime change, NAK import, M1 test, downstream rendering test or speed
benchmark is part of this cohort. Structural recognition does not qualify
arbitrary shaders. Additional operations, public library-factory integration,
native Apple resource identities and transparent applications remain open.
The next reception should apply the compiled reset producer to a real render
stream and verify the resulting image, before widening the accepted shaders.
