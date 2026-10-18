# Bounded overlap of two native Kepler kernels

The GTX 880M executed two native NVIDIA-compiled kernels with interleaved
lifetimes after an isolated change to our own uncommitted command stream.
The original shader instructions, installed driver and common KeplerMetal
runtime are unchanged. This is an explicit laboratory client (integration
level 1), not an implementation of the ordinary concurrent Metal encoder API.

## What changed

The ordinary native encoder serializes the two tested dispatches. Earlier
inspection found an intermediate `WAIT_FOR_IDLE`, but also found that ordinary
dispatches reused descriptor and constant-upload storage. Removing that wait
while reusing the same storage would not establish a correct concurrent path.

This client first uses the existing registered-library resident transport to
prepare **two separate records**. Each has its own 4,096-byte Private descriptor
allocation and 65,536-byte Private constant allocation. GPU blits read back the
256 active descriptor bytes and all constant bytes. The client and independent
Python verifier check the relocated native state, all three buffer bindings,
four disjoint allocations, 17 registers, the native 256-byte literal bank and
its retained native variant owner. Preparation submits NOP/copy work, with
zero user-kernel dispatches and untouched numerical witnesses.

Each resident launch contributes its original 24-byte launch/wait tail. After
checking the exact two-record stream and the uncommitted retained command
buffer, the client changes exactly one header at byte 16:

| Field | Original | Candidate |
| --- | --- | --- |
| Intermediate header | `0x20012044` (`WAIT_FOR_IDLE`, method `0x110`) | `0x20012040` (`NO_OPERATION`, method `0x100`) |
| Intermediate data | `0` | `0` |
| Final header/data, bytes 40/44 | `0x20012044`, `0` | unchanged |
| Descriptor addresses, shader and constant state | native validated values | unchanged |

These are method fields, not replacements of shader instructions. The method
names and values were checked against Mesa 26.2.4's public
[`cla0c0.h`](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-26.2.4/src/nouveau/headers/nvidia/classes/cla0c0.h),
SHA-256 `d40acf0020184a1d5b2039918d810be8e79707d8ba289cee984a265c368c9d58`.
The candidate is read back before commit and checked again after `endEncoding`.
The original terminal wait is retained. Descriptor/constant state is read back
before both candidate orders and after completion; its hashes stay identical.

The native `dispatchType` getter still returns serial (`0`). No capability is
spoofed. Our client uses the ordinary serial encoder as the carrier for this
specific resident-record experiment.

## Numerical and ordering witnesses

The published MSL contains `observe_a` and `observe_b`. Each dispatch has one
group of one thread. Atomic sequence tags bracket a bounded polling loop
(at most 4,096 iterations) and an integer arithmetic workload (128 rounds).
The kernels use atomic accesses for all communication between dispatches and
distinct output regions. A fresh nonce distinguishes every recorded trial.

The controls are no dispatch, A alone, B alone, serial A/B and serial B/A.
The serial first kernel exhausts the bounded poll; the second sees its peer.
For a candidate, the atomic order must satisfy both `A.begin < B.end` and
`B.begin < A.end`, with every tag present exactly once. The CPU independently
recalculates arithmetic, flags, bounded iteration counts, all output words,
unused guards and the complete parameter buffers and padding.

This witnesses **interleaved kernel lifetimes**. It does not measure simultaneous
instruction execution, SM occupancy, throughput, or CPU relief. The polling
work differs between controls and candidates, so their wall times would not
constitute a comparable performance benchmark.

## Qualification, 2026-10-18

The source baseline is public commit
`f8041705d59cc58c6582edb0d28d8982c94f6ad5` plus the new text files pinned in
[the validation summary](native-resident-overlap-validation.json).
The reference host used macOS 26.7.1 (25G241), SDK 26.2, Apple clang 17.0.0,
x86_64 and the existing restored NVIDIA stack.

| Cohort | Main trials | Correct user dispatches | Interleaved candidate pairs | Raw sync/output uint32 words | Intact guard words | Independently checked parameter bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Laboratory serial + three candidate processes | 69 | 110 | 34/34 | 35,328 | 34,241 | 100,352 |
| Separate public-source serial build/run | 20 | 24 | 0/0 | 10,240 | 9,988 | 40,960 |
| Same public artifact, candidate run | 21 | 38 | 16/16 | 10,752 | 10,385 | 43,008 |

The public core was rebuilt from all seven published runtime implementations,
with two MRC and five ARC objects. Its archive hash differs from the laboratory
archive. It received its own GPU qualification above; it does not inherit the
laboratory archive's other feature suites. The reference client executable
happens to be byte-identical after linking the subset it uses.

All successful hosts terminated normally without a kill request, and restored
the device scope. Main-trial totals exclude the separate 512-word untouched
preparation check in each process. The older laboratory serial baseline checked
its parameter padding in the native host but did not archive those parameter
arrays; its bytes are therefore excluded from the laboratory independent total.

Earlier development failures remain in the local evidence: one exception-cleanup
abort, one normal rejection caused by measuring the cursor before internal
resource setup, and one compile error. They are not counted as passing trials.
The final client closes its encoder in `@finally` and obtains the validated
stream start from the returned cursor and exact native-tail length.

## Reproduce from source

Use an existing licensed macOS/Xcode/driver installation. Dependency provenance
and recovery links are in [DEPENDENCIES.md](DEPENDENCIES.md). No Apple/NVIDIA
binary, captured command stream, compiled shader or private host configuration
is distributed. The following first two commands compile text only and execute
no GPU work:

```sh
python3 -m unittest discover -s tests -v
python3 tools/build_from_source.py --out build/resident-core
python3 tools/native_resident_overlap.py build \
  --core-build build/resident-core --out build/resident-client
```

Outputs must be fresh paths under `build/`. The second builder freezes the
complete core source snapshot, its archive, the MSL/host/verifier and launcher
inputs, regenerates AIR/metallib, and records hashes, commands and compiler
versions. It requires the source-built core to match the current checkout.

All GPU cohorts on a host must use **one common reservation root**. If an
existing laboratory already has one, pass that same directory, including
across checkouts. In a fresh single-checkout laboratory only, initialize
`bridge/results` and use `bridge` below. Do not create another reservation root
to evade an occupied lease. The lease coordinates participating lab processes;
it is not exclusive access against WindowServer or other applications.

```sh
mkdir -p bridge/results
python3 tools/native_resident_overlap.py run \
  --build build/resident-client --out build/resident-serial \
  --mode serial --trials 4 --reservation-root bridge
python3 tools/native_resident_overlap.py run \
  --build build/resident-client --out build/resident-overlap \
  --mode overlap --trials 8 --baseline build/resident-serial \
  --reservation-root bridge
python3 tools/native_resident_overlap.py audit \
  --build build/resident-client --run build/resident-overlap \
  --out build/resident-audit.json
```

The two `run` commands explicitly submit GPU work through the common leased,
immutable signed launcher. The final `audit` is CPU-only. The candidate requires
a separately audited 20-trial/24-dispatch serial baseline from the exact same
build, then repeats five controls in its own process before altering any wait.
Trial counts are bounded to 1–8; eight gives 16 candidate pairs across both
orders. A failed or uncertain run is retained: inspect its signed-process and
reservation status before attempting any further GPU run.

## Remaining work

The strict device/private ABI checks intentionally refuse an unknown GPU,
driver profile, native shader layout or stream. This is not a generic Kepler
API or a declaration that all concurrent workloads are correct. Only these two
one-thread kernels, bindings and resource lifetimes are qualified. The native
program ownership is retained; its instruction bytes are not independently
read back from VRAM by this experiment.

Next work is to define a general dependency/barrier contract, provide an
explicit reusable frontend, and qualify broader geometry, aliasing, lifetime
and failure cases before integrating the ordinary Metal factories. Transparent
application integration and a representative performance benchmark remain
separate milestones. The installed system, OCLP and common runtime are unchanged.
