# Native command compiler boundary: acceptance is not execution

The typed public MSL ICB argument still fails native NVIDIA pipeline creation.
Diagnostic kernels that reinterpret an ordinary buffer as a command object pass
pipeline creation instead. Their captured native programs contain a call with
local disassembly target `0x0`; this investigation does **not** establish a usable
native ICB path. No diagnostic kernel is dispatched. The working project-owned
[source command interface](NATIVE_RENDER_SOURCE_COMMANDS.md) remains separate.

This is compiler/runtime investigation relevant to branches A and B, with no
new functional GPU feature, performance claim or installed-driver modification.

## Controlled compiler matrix

The frontend is Apple Metal 32023.864, requested `macos-metal2.3`, with modules
disabled. SDK 26.2 / clang 17 / Python 3.9.6 run on macOS 26.7.1, build 25G241,
x86_64, GTX 880M PCI `10de:1198`. The exact driver SHA-256 is:

```
e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645
```

| Source case | Frontend/library | Native PSO | Captured main code |
| --- | --- | --- | --- |
| Ordinary pointer read/write control | Accept | Created | 192 bytes |
| Typed `command_buffer`: compute reset | Accept | Refused: `air.command_buffer` argument kind | No constructor program |
| Typed `command_buffer`: render reset | Accept | Same metadata refusal | No constructor program |
| Raw diagnostic: compute/render reset and copy, render draw and vertex binding | Accept | Six created | Six identical 64-byte blocks |
| Same six operations plus ordinary output witness | Accept | Six created | 128 bytes each; five identical, vertex-binding variant differs |
| Same ordinary witness without command operation | Accept | Created | 192 bytes, distinct from all command variants |

The raw form is a **diagnostic reinterpretation**, not an Apple-supported way to
create an ICB or a certified object representation. No opaque handle is supplied
or fabricated by the host. Merely changing the argument's visible type is not a
qualified implementation of the command contract.

The frozen AIR text keeps the six distinct operation calls and replaces the
indirect-buffer metadata with ordinary `air.buffer` metadata in raw cases. The
captured 64-byte programs have identical SHA-256:

```
1b6f9025968407ac177f00b260b9d6e246d0c5a044dd607d509f2a0cafd11513
```

The complete listings decode without unknown annotations. At native program
offset `0x8`, they contain `call lim 0x0`, followed by exit/padding. The witness
variants also retain a call at that offset. This target is a **local disassembly
value**, not proof of a physical GPU address or an executed loop. Do not label
these operations working, discarded as no-ops, or incapable in hardware based
only on this capture. Later resolution, native object representation and
instruction execution remain unqualified.

## Constructor and CPU-copy observation

REA 6.4.0 / Ghidra 12.1.4 analyzed the exact installed driver read-only. The native
constructor is at static address `0x10aa03`. Its compute variant's vtable at
`0x1c20e8` selects initializer `0x177f50` through slot `0x10`. The analyzed dataflow
copies section `0x10005` to a CPU staging allocation referenced at variant offset
`0x8a8`, using the byte count at offset `0x18`. Resource preparation is at
`0x176f1e`. These are artifact addresses/derived field offsets, not live addresses
or source-level NVIDIA declarations. [Evidence IDs and limitations](native-command-driver-evidence.json).

A narrowly pinned, process-local MRC observer passes every original constructor
argument and return value unchanged. It copies the constructor input, calls the
original method, reads only the returned object's own CPU staging allocation,
and restores the original method before returning to ordinary host work. The
fourteen post-constructor CPU copies match the captured program bytes exactly.
Both typed refusals restore the observer despite having no constructor program.

This rules out replacement of the observed CPU staging bytes during that
constructor comparison. It does not independently read resident GPU code,
attest the upload path or exclude rewriting/resolution at later binding/commit.
No private function is invoked by a guessed static address.

## Qualification scope

The final cohort comprises sixteen signed terminal nonoverlapping processes,
14 created PSOs, two exact metadata refusals and 14 post-constructor comparisons.
Nine matching cases agree with their noninterposed observations. Forty-six actual
signed processes including earlier cohorts/pilots are terminal without kill or
overlap; these are **construction observations**, not compute dispatches.
Application code creates no queue, command buffer, encoder or GPU resource via
resource factories. The zero-resource count excludes internal driver allocations.

All 212 portable CPU tests pass, including 13 malformed-container/classification
controls. The native parser rejects truncated data, overflow, broken links,
duplicate/missing code metadata and wrong stages. The 87 monitored system files
remain unchanged. The core runtime is not linked or changed. No M1/Qwen run,
benchmark, hardware video or system installation is part of this investigation.
[Exact counts and hashes](native-command-boundary-validation.json).

An intermediate CPU-only capture-host build failed because a string literal
lacked whitespace before an Objective-C selector; the corrected fresh build
passes. One initial offline audit expected all six witness variants to match;
the final evidence preserves the differing vertex-binding variant instead.
Neither failure is a failed GPU execution.

## Reproduction

Use a new work directory and the existing common physical-device reservation.
Every Metal host, including construction-only probes, must be signed, immutable
and terminal before the next launch. No GPU execution option is provided.

```sh
python3 bridge/tools/public_native_command_boundary.py build \
  --out "$KP_WORK/plain-build"
python3 bridge/tools/public_native_command_boundary.py build --capture \
  --out "$KP_WORK/capture-build"
python3 bridge/tools/public_native_command_boundary.py run \
  --build "$KP_WORK/capture-build" --out "$KP_WORK/captured/raw_render_reset" \
  --case raw_render_reset --reservation-root "$KP_LAB"
```

Run the sixteen `CASES` from the tool in fresh subdirectories for the captured
cohort. Run at least the first nine cases without capture in a separate observation
cohort. The runner freezes source, AIR text, metallibs, host, launcher and oracle;
validation uses an isolated interpreter. Source builds perform no Metal API work.

```sh
python3 bridge/tools/audit_native_command_boundary.py "$KP_WORK/captured" \
  --build "$KP_WORK/capture-build" --observation "$KP_WORK/plain" \
  --out "$KP_WORK/audit.json"
python3 -m unittest discover -s tests -p test_native_command_boundary.py -v
```

Disassembly is optional CPU analysis using the separately obtained envytools
revision documented in [dependencies](DEPENDENCIES.md); select `gf100` / `gk104`.
Compiled shaders, captured programs, resident data and NVIDIA/Apple binaries are
not included in this source release. The REA private evidence bundle and analysis
snapshot likewise remain outside the public repository; only factual addresses,
identities and evidence references are published.

## Next work

Inspect later native binding/linking before any candidate execution; preserve the
metadata and raw controls. In parallel with that question, examine strict AIR
lowering of one typed command operation to the existing certified record ABI.
Simply bypassing argument metadata, changing capability flags or accepting a PSO
cannot supply correct ICB resource management and execution. The complete
modernized-driver and GTX hardware-coverage objective remains open.
