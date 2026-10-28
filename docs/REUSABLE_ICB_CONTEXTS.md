# Reusable ICB contexts with generation and submission lifetimes

An opt-in CommandIR mode now keeps one owned Private context buffer per
compute ICB across completed generations. An adapted application can reuse its
ICB and public argument encoder while changing the native template catalogue,
parameters, buffers and geometry. Old CPU plans are rejected after reset;
old generation-tagged roots are rejected by the native NVIDIA-compiled producer.
This is a project ABI extension, not Apple's ICB resource-ID representation.

A separate [experimental producer-only abandonment operation](REUSABLE_ABANDON_API.md) is available under a strict cooperative ownership contract. General cancellation remains unsupported.

## Encoding contract

The workspace `metal_command_buffer` header is compiled with
`KP_COMMAND_TAGGED_CONTEXT=1`. The original MSL call sites are retained, but
`command_buffer` becomes a UInt64 handle: low 40 bits are the owned context's
GPU virtual address and high 24 bits are a process-local generation. The native
48-byte root reflects `[ULong, ULong, Pointer, Pointer, Pointer, Pointer]`.
An explicit reusable-function registration selects this schema. Ordinary native
function registration/encoders reject this schema and preserve the pointer ABI.

The context remains 480 bytes. Magic `0x4b505243` identifies this variant;
`base.version = (generation << 8) | 4`. Generation zero is invalid. A single
linked runtime assigns monotonically increasing generations, saturating after
`0xffffff`; it never wraps or reuses a value. Exhaustion is an explicit failure,
not recovery or a persistent cross-process identity. The producer checks magic
and the full packed generation before any record access. The table and executable
records otherwise use the existing stable-ID/version-2 formats and materializer.

Build the native producer with `-fmodules=none` when using the workspace header.
The reproduction builder does this for every source that includes this header,
including refusal probes. During development a compiler module from a previous
build retained that previous header's definitions and caused redefinition errors.
Disabling modules for these bounded source builds avoids sharing that state;
SDK files and system/module caches were not edited or removed. Ordinary opaque
Metal sources retain their original compilation options and pinned fixtures.

## Required lifecycle

1. Prepare original registered source and destination templates with the existing
   resident API. Use `newGPUReusableCommandIRFromBuffer:...` for the destination.
   Its first successful allocation stays attached to that ICB.
2. Register the exact compiled producer using
   `newReusableCommandIRFunctionWithLibraryData:expectedSHA256:functionName:rootBufferIndex:error:`.
   Create the native PSO through an ordinary factory and bind roots through that
   function's public argument encoder. Finish and validate all roots.
3. **Before encoding the producer**, call
   `reserveCommandIRProducerInCommandBuffer:error:` on the plan. Declare all
   indirect resources as for the existing native producer path.
4. Call `encodeCommandIRInCommandBuffer:afterProducer:error:`. The materializer
   must follow the producer on the same retained queue. Adapted consumer encoders
   automatically reserve their actual command buffers before executing records.
5. Only after every tracked producer, materializer and consumer CB completes
   successfully may the application reset or mutate the destination and prepare
   a new generation. The public argument encoder can bind it again; its old plan
   is no longer usable.

The owner thread, queue and retained-reference requirements are explicit. The
lease retains pending command buffers, resources and itself through completion.
A recorded but uncommitted consumer is still pending even if the materializer
has already completed. An uncommitted CB ordinarily must eventually be committed
because it could otherwise be submitted later. The experimental operation may
abandon only an exclusive unmaterialized producer under its strict contract;
it does not cover general pending buffers.
Dropping a plan does not release its pending lease. Command errors poison the
context; allocate a fresh ICB rather than reusing that context. Wrong-thread,
foreign-queue, unretained and inactive-generation reservations are refused.
Ordinary CPU/GPU command-state copying involving a reusable command is refused;
GPU `compute_command.copy_command` inside the same active generation is tested.

Any destination mutation conservatively retires its whole generation. The slot
keeps its lease/generation link until a successful reset. In particular, a
rejected direct setter must not detach it and permit later consumer encoding
from a retired generation. Each GPU trial checks that setter refusal followed
by a one-slot consumer refusal (80 cases across the reusable cohort). Old plans
also check that their target's current argument context still belongs to them.
Completion callbacks synchronize against the lease and remove only their own
matching CB, so a late callback cannot release a newer pending submission.
Preparation releases its synchronization lock before waiting for initialization;
there is no lock held across that GPU wait.

This remains a cooperative application contract. Raw exported roots must retain
their owned resources, and all producers/consumers must use this API. The handle
is not an arbitrary-pointer validator, a security token, cancellation support,
a cross-queue synchronization mechanism, or a general shader translator. Private
native ABI/profile checks and the 40-bit address bound remain mandatory.

## Qualification and reproduction

See [machine-readable qualification](reusable-icb-context-validation.json).
The runtime is a complete source build of all seven objects, archive SHA-256
`b64ccfc0e73dc82b5cd5e4ffeb315e1fb23f93de0e48febe385031c73a6743a4`.
Only `KeplerCPUICB.o` differs from the preceding qualified archive. Environment:
macOS 26.7.1 / 25G241, SDK 26.2, clang 17, x86_64, GTX 880M PCI `10de:1198`,
exact installed driver `e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645`.

The final reusable cohort has 20 signed processes and 80 generations on the
actual GTX: **6,411,264 exact consumer uint32 values**, 1,602,816 consumer
invocations and 103,562,368 intact guard bytes. Each process keeps exactly the
same context GPU virtual address through its four generations. All 464 premature
prepare/reset attempts are refused, as are 60 retired CPU plans. Three prior
roots are rejected by GPU generation checks; their record regions remain
canaries and their consumer counters stay zero. The delayed-consumer case
verifies completed materialization while its recorded consumer remains pending.
These checks exercise recorded command-buffer ownership; the mock CPU cases
separately cover in-flight status values without inducing GPU errors.

A separate 32-process regression on this same runtime repeats the full preceding
stable-ID/record/function/NAK matrix. The auditor additionally compares 48 raw
stage/counter files from reusable current-generation runs against their pointer
counterparts; the regression compares those pointer counterparts against both
NAK routes. The aggregate receipt requires all 52 processes terminal and
nonoverlapping. Pilot runs are excluded from these counts. There is no new M1
hardware run in this phase. All 129 portable CPU tests and the C11 ABI compilation
pass; all 87 tracked system reference files retain their starting hashes.

The builder also compiles 16 CPU-only cases against the actual lease implementation
using explicitly mocked command buffers. Those cover busy statuses, duplicate
reservation, completion, stale generation, foreign queue/thread, unretained CB,
error poisoning, late callbacks and plan-independent lifetime. They are not GPU
execution evidence. Portable receipt tests reject missing or contradictory
lease records, changed physical buffers, repeated generations and a false
completed-materializer control. GPU raw readbacks are checked separately.

Use a fresh output directory for each build and process. Obtain original local
fixtures as described in [dependencies](DEPENDENCIES.md); they are not included
in the public repository. Builds do not submit GPU work:

```sh
python3 tools/build_from_source.py --out build/reusable-contexts
python3 bridge/tools/public_native_msl_commands.py build \
  --library build/reusable-contexts --assets "$LOCAL_ASSETS" \
  --out "$NEW_BUILD" --function-arguments --stable-identities \
  --reusable-contexts --nak-baseline
python3 bridge/tools/public_native_msl_commands.py run \
  --build "$NEW_BUILD" --out "$NEW_RUN" \
  --reservation-root "$COMMON_LAB_BRIDGE" --kind reusable --mode basic
```

Omit `--nak-baseline` for a native-only build with the six original native fixture
files. The 20 reusable modes are `REUSABLE_FLOW_MODES` in the builder. In addition
to the 18 preceding stable-ID dataflow modes, `delayed_consumer` completes the
materializer, records a consumer on a separate CB, and verifies both prepare and
reset still refuse until that consumer completes. `stale_root` submits the prior
generation's root against the same live owned context for three trials:
records remain canaries, consumers do zero work and all guards stay intact.
The first trial is a valid current-generation positive control.

For the complete cohort, store these 20 runs under `reusable/<mode>` and the
preceding 32-host matrix under `regression/` using its documented case names:

```sh
python3 bridge/tools/audit_reusable_icb_contexts.py "$COHORT" --out "$NEW_RECEIPT"
```

The CPU-only auditor recomputes numerical outputs, full contexts, roots, records,
native binding images, guards, counters and witnesses, compares current-generation
results with the pointer/NAK paths, verifies exact hashes and requires signed,
terminal, nonoverlapping hosts. It does not create new hardware observations.
Failed builds, a complete intermediate 52-host cohort and pilot controls are
preserved outside the final cohort. A same-current-client before-control linked
against the intermediate archive
`c10d75eefbb4e39c370d3f807acdabaf00439a606009e12868fc19f3212c48d3`
reproduces the retired-slot defect at expected exit 35: the direct setter rejects,
but a subsequent one-slot consumer encoding does not. That consumer CB is never
committed. The signed runner correctly treats exit 35 as a failure; its saved
manifest independently confirms terminal state and no forced termination before
the corrected cohort starts. The corrected archive differs only in the ICB
object, with identical producer/fixture asset hashes and the same client source.
The final cohort checks both refusals in every reusable trial. These tests concern
this targeted own-process lifecycle path, not an installed-driver repair.

## Remaining integration

This is level 2 adapted-application support. The installed NVIDIA driver, Apple
frameworks and OCLP are unchanged. Native ICB/PSO `gpuResourceID`, transparent
unmodified applications, general library/compiler support, cross-queue/concurrent
encoding, cancellation/error recovery and broader hardware qualification remain
open. Preparation still captures native descriptors and waits; reusing one
context buffer is not an allocation-free frame path. No speedup, throughput
benchmark, global Metal 3/4 support or hardware-video progress is claimed.
