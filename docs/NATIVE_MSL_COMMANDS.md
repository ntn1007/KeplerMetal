# Command producers compiled by the native NVIDIA backend

The supported public MSL `compute_command` call sites can now produce the
existing CommandIR v2 records through the installed NVIDIA compiler, then drive
the existing GPU materializer and registered native consumers on the GTX 880M.
The native producer uses no NAK compiler, SM30 program import or constructor
replacement. This is a new opt-in source-lowering backend, not a change to the
installed NVIDIA binary or Apple's original ICB representation.

The unchanged source calls are in `gpu_command_frontend_dataflow.metal`.
`KeplerNativeMSLCommands.h` supplies original implementations of a bounded command
API. A workspace-only include directory selects it for subsequent source tokens;
the SDK definitions are kept intact in their original namespace. The compiler
then sees ordinary pointers/scalars and global-memory operations instead of the
unsupported `air.command_buffer` argument kind. A previously refused minimal
reset kernel creates an actual `NVMTLComputePipelineState` and an 8-byte native
argument encoder through this path. Construction alone was followed by the GPU
record and consumer tests below.

## Lowering and the pointer-address contract

The CPU ABI header remains the single record-layout definition. The builder
copies it locally, replacing only its system `stdint.h` include with the two
matching MSL integer typedefs. Sizes and important offsets are compile-time
asserted. The source/core ABI header and seven-object runtime are unchanged.
The native helpers implement reset, same-context copy, registered pipeline
tokens, four buffer slots, threadgroup/grid dispatch fields, shared-memory slot
0, barrier flags and stage-in fields. They preserve the existing error codes.
Stage-in fields and other record-only operations are not thereby qualified for
execution by every materializer/profile.

The first full record probe exposed a real mismatch in our initial lowering:
the numerical address stored for `constant_pointer + 3` lost its high word.
For three cases only, record byte offset 108 was zero instead of the expected
high address word. The completed process and all raw records are preserved;
the CPU verifier rejected them. This observation does not establish a general
bug in native constant-buffer dereferences or a hardware limitation: our wire
ABI requires GPU virtual addresses, while a constant-space pointer's numerical
representation was not a sufficient basis for that contract.

The corrected builder lowers only registered, immutable GPU-buffer members in
the argument structures from `constant uint *` to `device const uint *`.
It verifies their type, name, ID and occurrence count. Shader method calls,
kernel constant arguments, global constant variables and SDK files are not
rewritten. Remaining constant-space `set_kernel_buffer` bindings and strided
overloads fail compilation explicitly. This is not a global keyword replacement
or a claim of arbitrary MSL address-space compatibility. The host must retain
the registered GPU buffers and keep these inputs immutable until completion.

The supported producer profile has one writer per record. Context magic/version,
capacity, stride and SM30 address-domain checks precede record access. Record
magic, token, buffer-slot, shared-slot and same-context-copy checks preserve
the error contract. These checks do not validate arbitrary shaders or fabricate
ownership of an arbitrary GPU address; the existing host resource catalogue and
materializer checks remain required.

## Final GPU qualification

Reference: macOS 26.7.1 / 25G241, SDK 26.2, Metal compiler 32023.864,
clang 17, baseline x86_64, PCI `10de:1198`, exact driver profile `e240d54a…`.
The final matrix uses 22 signed terminal nonoverlapping processes. The consumers
and transport are linked against the already-qualified complete archive
`70818a656f9cb518d77da924cb48f0225ba78a5a2c5fc1b24370675aaa8e58c4`;
all its source hashes remain unchanged. Nineteen old fixture hashes are checked
for the full comparison; only six native fixtures are required for a native-only
build. [Machine-readable results](native-msl-command-validation.json).

A separate native-only build contains neither archived `.sass` programs nor a
NAK comparison executable. Its additional signed basic-chain process passes
457,728 exact uint32 results and 5,052,992 guard bytes. These extra results are
reported separately from the 22-process table. One hundred twelve portable
CPU tests pass; all 87 system references remain unchanged. No fresh M1 run or
performance benchmark was performed.

| Cohort | Processes | Checked evidence |
| --- | ---: | --- |
| Native record generation | 3 | 69 cases, 46 dispatches; 141,312 record bytes and 105,984 guard bytes compared independently |
| Native producer → materializer → consumers | 16 | 5,035,008 exact consumer uint32 results, 1,258,752 active consumer invocations, 81,473,504 checked guard bytes, 8 API refusal controls |
| Previous NAK producer reference | 3 | 1,373,184 exact consumer uint32 results; 48 stage/counter files match the native backend byte for byte |

The record cases cover complete addresses and pointer arithmetic, both dispatch
field kinds, barriers/clear, shared slot, stage fields, copy/reset ordering,
self-copy, unready records, invalid tokens/slots, foreign-context copy,
out-of-range index and invalid context metadata. Invalid-index tests remain
inside physically allocated guard storage even if a check fails. These programs
write inert record data; those record-only cases never submit their generated
descriptions as GPU commands. A no-dispatch process must leave all bytes at the
initial marker. Two compiler-only cases verify the specific deleted-overload
refusals, not merely an arbitrary nonzero exit code.

The consumer matrix exercises a three-stage GPU data dependency with 256,
1,024, 4,096 and 32,768 elements, including 33-thread and 1,024-thread groups.
It covers basic/barrier/copy, omitted stages, a separate producer command buffer,
missing producer/consumer, malformed record fields and host API refusals. The
native program writes descriptors, resource bindings and geometry on the GPU;
the CPU neither reads those records between stages nor uploads expected output
values. The unchanged materializer accepts only the retained pipeline/resource
catalogue and registered bounds; invalid record controls remain rejected.
Initial resource setup waits are distinct from the zero intermediate waits
between producer, materializer and consumers.

Eight API refusal cases remain explicit. Missing or invalid work matches its
own CPU oracle and leaves the expected regions/counters unchanged. Full CB1
bindings, materializer witnesses, records, dummy buffers and data guards are
checked by the portable dataflow auditor. Forty-eight complete stage/counter
files from basic, barrier and copy match the old NAK path. This is a correctness
comparison; no throughput or CPU-overhead benchmark was performed.

## Reproduction

Obtain the existing locally generated native fixtures using the source workflows
in [BUILDING.md](BUILDING.md) and [DEPENDENCIES.md](DEPENDENCIES.md). They are not
redistributed. `native_msl_fixture_pins.json` lists the required exact hashes;
the script does not download, silently repin or regenerate unknown fixtures.
Native producers and record probes are built freshly from the published text.
A clean-checkout bootstrap of all historical fixture trees is still incomplete.

Set `KP_WORK` to a new directory, `KP_ASSETS` to the verified fixture directory
and `KP_LAB` to the existing common reservation root. Build the complete runtime
from source or use its exact, source-matching qualified build. For the complete
22-process comparison, include the optional archived NAK baseline:

```sh
set -e
python3 -B tools/build_from_source.py --out build/native-msl-local
mkdir "$KP_WORK"
python3 -B bridge/tools/public_native_msl_commands.py build \
  --library build/native-msl-local --assets "$KP_ASSETS" --nak-baseline \
  --out "$KP_WORK/build"
mkdir "$KP_WORK/accepted"
kp_run() {
  label="$1"; kind="$2"; mode="$3"
  python3 -B bridge/tools/public_native_msl_commands.py run \
    --build "$KP_WORK/build" --out "$KP_WORK/accepted/$label" \
    --reservation-root "$KP_LAB" --kind "$kind" --mode "$mode"
}
kp_run records-execute-0 records execute
kp_run records-execute-1 records execute
kp_run records-no_dispatch records no_dispatch
for mode in basic barrier copy no_seed no_gather no_finish split no_producer \
            no_consumer bad_parameters bad_counter bad_pipeline \
            bad_buffer3_flag bad_groups bad_reserved refusals; do
  kp_run "native-$mode" dataflow "$mode"
done
for mode in basic barrier copy; do kp_run "nak-$mode" nak "$mode"; done
python3 -B bridge/tools/audit_native_msl_commands.py "$KP_WORK/accepted" \
  --out "$KP_WORK/native-msl-audit.json"
```

Omit `--nak-baseline` for a native-only build, requiring no archived NAK programs
or NAK toolchain. Use only `dataflow` and `records` runs in that case; the full
matrix auditor intentionally requires its three NAK reference cases. Every run
uses the common immutable signed launcher and cooperative host lease. Stop and
inspect the exact process/session after any failure; never overwrite failed
evidence or restart based only on an observation timeout.

## What remains

This is adapted-client integration with a distinct CommandIR ABI. Original
Apple ICB identities, stable public `gpuResourceID` for the command/pipeline
objects, automatic loading of arbitrary shipped metallibs and transparent
ordinary-application integration remain open. Rendering commands, imageblocks,
arbitrary root schemas, strided bindings and constant-memory objects outside
the registered immutable-buffer profile are not implemented here. The existing
transport remains serial with its per-record wait; barrier flags do not enable
general GPU concurrency. No system driver, family flag, OCLP or WindowServer
component was changed. This does not establish full Metal 3/4 support or a speedup.
