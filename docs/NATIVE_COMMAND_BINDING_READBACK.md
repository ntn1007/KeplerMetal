# Native command code through binding and private-buffer readback

The preceding [compiler-boundary investigation](NATIVE_COMMAND_COMPILER_BOUNDARY.md)
left open whether native binding would resolve the diagnostic command programs.
The fourteen ordinary/raw/witness shaders now have owned code-buffer inspection,
uncommitted compute encoding and private-buffer readback before/after encoding.
The code bytes remain unchanged in the tested stages. This is diagnostic driver
and compiler work, not native ICB execution or a new Metal feature.

## Owned resource and execution boundary

REA 6.4.0 / Ghidra 12.1.4 inspected the exact driver `e240d54a…`. At static address
`0x171858`, the allocator constructs an `NVMTLBuffer` with options `0x21`. The
compute variant stores the buffer at `+0x898`, its CPU code copy at `+0x8a8`,
code GPU address at `+0x10`, size at `+0x18` and code offset at `+0x24`.
[Exact profile, evidence ID and field mapping](native-command-binding-driver-evidence.json).
These are derived field interpretations, not NVIDIA source declarations.

The host reads only its own pinned pipeline/variant. It checks the native class,
owner back-reference, registered Objective-C object class, buffer protocol,
device identity, GPU address relation and complete code range. All tested code
buffers report **Private storage mode 2**. No code buffer is forged or modified;
only its validated code range is read, never neighboring allocation contents.

The optional readback creates an independent command buffer with a blit encoder,
copies the code into a Shared buffer between 64-byte guards, commits that blit CB
and waits for completion. The suspect compute CB is **never committed or enqueued**.
The submitting helper cannot receive it, and the host rechecks its NotEnqueued
status after both readbacks. No mode can submit the suspect compute dispatch.
The missing-copy control submits empty blit work and retains all `A5` bytes.

This retrieves data through Metal from the GPU-addressable private code buffer;
it does not independently observe instruction fetch, physical VRAM placement,
instruction-cache state or commit-time rewriting of a future compute submission.

## Results

The final cohort has **60 signed terminal nonoverlapping hosts**:

- Fourteen resource inspections and fourteen uncommitted encoding cases.
- Two fresh fourteen-shader readback series.
- Four missing-copy controls covering ordinary code, raw reset, reset witness
  and the distinct vertex-binding witness.

There are **56 matching code readbacks / 6,144 code bytes**, **8,192 intact guard
bytes**, and **28 identical readback file pairs** between the fresh series.
Sixty-four blit CBs complete: 56 contain a copy and eight are empty controls.
The CPU code and code-buffer identity remain unchanged across all 244 snapshots.
Forty-six compute dispatch calls are encoded in CBs that remain NotEnqueued;
**zero compute dispatches are submitted**. Their offline-decoded QMDv00_06
program-offset field matches the variant's GPU code address low32, and geometry
and register counts match the observed pipeline. QMDs are not replayed or edited.

All fourteen shader libraries and constructor code hashes match the preceding
compiler cohort. Three separate pilots precede the final cohort: **63 actual
signed terminal hosts** in total, without kill or overlap. The 228 portable CPU
tests pass, including 16 new QMD/call-decoding controls. Eighty-seven monitored
system files are unchanged. [Exact counts](native-command-binding-validation.json).

## The call remains in the retrieved bytes

The six raw command operations and their six witness variants retain the
instruction word `0x5003ffffc0011c07` at local program offset `0x8`. A separate
small decoder uses the [pinned envytools opcode and target definitions](https://github.com/envytools/envytools/blob/f102b82381f3f11cee113d16374c87091db039d9/envydis/gf100.c#L1887):
its displacement is signed 24-bit at bit 26, added to PC plus eight. The encoded
displacement is `-16`, so the target is local program offset **zero**. Tests
explicitly relocate the same word to distinguish this from absolute GPU zero.
The [target-field definition](https://github.com/envytools/envytools/blob/f102b82381f3f11cee113d16374c87091db039d9/envydis/gf100.c#L46)
is independently checked alongside the earlier full disassembler listings.

All **48 raw-operation readbacks** have this PC-relative target at program entry;
the eight ordinary-control readbacks do not have that call at the tested offset.
The scope is the stored/selected program through uncommitted encoding. This does
not prove that a later commit cannot rewrite it, establish executed recursion,
or qualify the raw object representation as an Apple ICB ABI. No such program
is launched to infer these semantics from a hang or fault.

## Reproduction

Use the current x86_64 reference system, SDK 26.2 and the same existing physical
GPU reservation. The standalone build regenerates the fourteen MSL 2.3 shaders,
MRC host and frozen oracles without launching a Metal host:

```sh
python3 bridge/tools/public_native_command_binding.py build --out "$KP_WORK/build"
python3 bridge/tools/public_native_command_binding.py run \
  --build "$KP_WORK/build" --out "$KP_WORK/inspect" --case raw_render_reset \
  --mode inspect --reservation-root "$KP_LAB"
```

After inspecting that terminal result, use fresh directories with `encode`,
then `readback`. `readback_no_copy` is the explicit negative control. All hosts
use immutable signed executables, common inherited reservations and fresh
isolated frozen-oracle validation. Stop and inspect the exact terminal/session
if execution or validation fails; do not restart on an observation timeout.

For the full audit, use subdirectories `inspect`, `encode`, `readback-0` and
`readback-1`, each containing every `CASES` shader directory. `no-copy` contains
`pointer_control`, `raw_render_reset`, `raw_render_reset_witness` and
`raw_render_vertex_witness`. Its actual mode is `readback_no_copy`. The explicit
reference is the prior `post-constructor-cohort` described in the compiler doc.

```sh
python3 bridge/tools/audit_native_command_binding.py "$KP_WORK/cohort" \
  --build "$KP_WORK/build" --reference "$KP_REFERENCE" --out "$KP_WORK/audit.json"
python3 -m unittest discover -s tests -p test_native_command_binding.py -v
```

## Remaining work

The typed ICB metadata refusal from the previous investigation is not repaired.
The raw reinterpretation is diagnostic, not a native resource contract. Its
relative entry call is still present in private-buffer readback through encoding.
Any compatibility implementation must provide valid command resources and
semantics; bypassing a type or accepting a PSO does not establish those.

Next work is strict AIR lowering of a typed operation to the already qualified
record contract, retaining native/reference controls and investigating any later
binding/commit resolution as needed. The original shader and system files must
remain preserved. Full native ICB semantics, transparent application integration,
Metal 3/4 conformance and the complete hardware goal remain open. No performance
claim, new hardware-video result, Qwen/M1 run or installed-driver modification
is part of this cohort.
