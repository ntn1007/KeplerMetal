# Typed AIR render-command reset on Kepler

An unchanged, SDK-typed shader containing `metal::render_command.reset()` now
executes through a strictly pinned AIR translation and the NVIDIA native
compiler on the GTX 880M. The caller supplies a **project context**, not an Apple
ICB resource. This is a first compiled-shader compatibility experiment for
branch B, with explicit adapted-application integration. No installed driver,
SDK header, OCLP setting or core runtime archive changes.

## Translation and evidence

`public_air_render_reset.py` reconstructs the original shader from
`public_native_command_boundary.source('typed_render_reset')`. Bounded indexed
extraction validates its library/AIR hashes. Apple Metal disassembles the AIR;
`lower_air_render_reset.py` accepts exactly one normalized IR SHA-256 profile.
The normalization removes only the module-path line and normalizes newlines.
Unknown bodies, operations, layouts and toolchain output are refused.

The lowering changes the root argument description from an indirect command
resource to an ordinary eight-byte buffer and replaces the reset intrinsic
with an internal checked helper. The original entry's argument load and index
remain. Apple Metal inlines the helper and emits ordinary loads/stores; NVIDIA
compiles that AIR into a native PSO. There is no NAK program import or native
instruction patch. The original shader source is never rewritten.

A construction-only process captures the native compiler output and its
post-constructor CPU copy. An offline section parser verifies zero alignment
padding, code/metadata bounds and copy equality; envytools disassembles the
program. The inspection certificate pins the library, native code, driver and
inspection evidence. The execution host reconstructs the PSO, checks the same
code hash and restores its temporary observer before creating a queue. The
certificate is a local qualification receipt, not a signature or sandbox.

The translated program has 960 native bytes; the independently written MSL
reference has 1,024. Neither inspected program contains a decoded CALL or an
unknown instruction. These byte counts are **not performance measurements**.
Native staging-code observation is not an instruction-fetch trace. Actual GPU
execution is established by guarded Private-buffer effects, CPU comparison,
reference comparison and missing-dispatch controls.

## Project context contract

Buffer 0 contains one 64-bit GPU address of a live, retained 32-byte context:

| Offset | Type | Meaning |
| --- | --- | --- |
| 0 | uint32 | Magic `0x4b505243` |
| 4 | uint32 | Version 1 |
| 8 | uint32 | Capacity, 1–16 |
| 12 | uint32 | Record size, 64 bytes |
| 16 | uint64 | Sixteen-byte-aligned record GPU address |
| 24 | uint64 | Reserved, zero |

Each active one-dimensional invocation resets its indexed 64-byte project
record to zero if the index is below capacity. Empty records are compatible
with the existing render-state record representation; this cohort does not
run a downstream renderer. The address-domain check bounds the maximum
16-record span below 2^40. It does not validate arbitrary GPU addresses: the
host must own and retain both allocations and declare indirect resources.
Concurrent reset/draw, duplicate writers, arbitrary contexts and resource
reuse across overlapping command buffers are outside this qualification.

## Reception

On macOS 26.7.1/build 25G241, SDK 26.2, Apple Metal 32023.864,
clang 17.0.0, NVIDIA driver SHA-256
`e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645`:

- Ten final signed, terminal, nonoverlapping hosts: two inspections, two
  missing-dispatch controls and three execution pairs.
- 84 compute dispatches in 120 completed command buffers; 42 dispatches belong
  to the AIR-translated variant and 42 to the native MSL reference.
- 138,240 readback bytes checked against the CPU, including 15,360 guard bytes;
  zero mismatches. The 11,856 changed bytes occur only in the expected records.
- 45 identical translated/reference output file pairs, 60 repeat pairs, and
  15 identical missing-dispatch reference pairs.
- Capacities 1/4/7/16, prefix/full reset, excess indices, empty work, null root,
  invalid magic/version/capacity/size/reserved field, null and misaligned record
  addresses. Invalid tests use valid owned context allocations.
- Per case, requested Private storage is 1,152 record/guard bytes plus 32
  context bytes. This is requested buffer size, not measured physical VRAM use.
- 249 portable CPU tests pass, including 21 new profile/parser/oracle tests.
  All 87 inventoried system-file hashes remain unchanged.

Two additional pilot hosts are preserved separately. The first construction
host succeeded without dispatch, but its frozen CPU verifier rejected final
zero alignment padding. The new parser accepts only checked eight-byte section
alignment with zero padding; the old failed receipt remains unchanged. A
second pilot executed 14 translated dispatches correctly. Counts above exclude
both pilots. The exact original library matches the preceding compiler-boundary
profile, where native typed PSO construction was refused at `air.command_buffer`.

Machine-readable results and hashes: [validation](air-render-reset-validation.json)
and [source provenance](air-render-reset-source-chain.json).

## Reproduction

Requires the local Xcode/Metal toolchain, the qualified restored NVIDIA driver,
an envytools `envydis` supporting GK104, and the existing shared reservation.
Use fresh paths on a disk with space. Build and certification are CPU-only;
inspection and execution hosts both use the shared signed launcher.

```sh
python3 bridge/tools/public_air_render_reset.py build --out /absolute/fresh-build
python3 bridge/tools/public_air_render_reset.py run \
  --build /absolute/fresh-build --out /absolute/session/inspect-lowered-02 \
  --reservation-root /absolute/common-lab/bridge --variant lowered --mode inspect
python3 bridge/tools/public_air_render_reset.py certify \
  --run /absolute/session/inspect-lowered-02 --envydis /absolute/envydis
python3 bridge/tools/public_air_render_reset.py run \
  --build /absolute/fresh-build --out /absolute/session/cohort/execute-0/lowered \
  --reservation-root /absolute/common-lab/bridge --variant lowered --mode execute \
  --certificate /absolute/session/inspect-lowered-02/certificate.json
```

Create the output parent directories first. Repeat inspection/certification for
`reference`, then run both variants in `no_dispatch` mode under
`cohort/no-dispatch/{lowered,reference}` and `execute` mode under
`cohort/execute-{0,1,2}/{lowered,reference}`. Run sequentially and stop on any
unresolved host/lease or failed verifier. Then:

```sh
python3 bridge/tools/audit_air_render_reset.py /absolute/session \
  --build /absolute/fresh-build --out /absolute/fresh-audit.json
python3 -m unittest discover -s tests -v
python3 tools/check_publication.py
```

## Remaining work

Only one exact shader is accepted. Additional operations, real shader control
flow/dataflow, public library-factory integration and downstream render
reception need separate qualification. Apple ICB resource identities and
argument encoders are not implemented by this translation. Transparent ordinary
applications, a replacement system driver, full Metal 3/4 and performance gains
remain open. The logical next experiment preserves a typed producer's other
arithmetic/control flow while lowering reset, before broadening recognition.
