# Stable pipeline identities resolved by native GPU producers

An opt-in CommandIR mode gives each retained native pipeline a stable identity
inside an active scope. The identity survives template permutations and multiple
prepared plans. The NVIDIA-compiled producer resolves it on the GPU into a
validated plan-local executable record. Applications can bind the same pipeline
object through public function encoders without constructing positional tokens.
This is a KeplerMetal identity namespace, not Apple's `gpuResourceID` or ICB ABI.

## Representation and ownership

`commandIRIdentityForPipeline:error:` accepts only native profiles owned by the
active IR scope. Repeated queries return the same value. A process-local atomic
counter in the supported single linked runtime assigns a nonzero 32-bit ordinal
under the `0x4b505350` tag, saturating before wrap. Closing a scope makes further
queries fail; a later scope obtains new values. Keep these values as UInt64; JSON receipts need a lossless integer parser.
IDs are not persistent,
serializable across processes, or interchangeable with native Metal resource IDs.
Nil, unregistered producer PSOs and restored scopes return zero with an error.
The existing profile catalogue retains pipeline objects, preventing pointer-key
reuse while that scope is active. There is no per-pipeline unregister API.

`newGPUStableCommandIRFromBuffer:...` chooses the mode at plan construction,
before any root is exported. Its owned Private context is 480 bytes: the same
reflected 32-byte base followed by eight 56-byte identity/parameter/geometry
entries. A different magic plus version 3 identifies this extension. An old
version-2 context stays 32 bytes; an old magic paired with version 3 remains
invalid. Unused entries are zero. The context and its table stay immutable until
completion and are declared as indirect resources by the existing producer path.

The root ABI remains `{context pointer, 64-bit token, buffers...}`. Native
reflection remains authoritative, including the original base type's seven
fields. The existing public argument encoder retains resources and validates
complete root bytes before submission. Stable roots for the same pipeline,
parameter binding and resource bank are identical even when several templates
have different local/grid requirements. The encoder admits this case only in
the stable mode; ordinary positional roots retain their ambiguity refusal.

The source-lowered MSL header first finds the stable identity, then refines its
selection after buffer, geometry and shared-memory setters. Parameter address,
local size, grid bounds and requested shared state distinguish template entries.
Setters may arrive in different orders. Identical matching entries use the first
match. Incomplete or unmatched state remains incomplete/invalid for the existing
materializer rather than being silently filled in. An unknown identity sets the
existing sticky error 1; reset is required to clear it. Same-context copy/reset
semantics remain unchanged.

The producer writes the original version-2 record token (`0x4b504950`, candidate
index), never an unresolved stable handle. The materializer binary, native
command transport, resource bounds, full native binding images and per-record
serialization remain unchanged. No new arbitrary packet format or driver method
is introduced. Bounds and lifetimes remain cooperative contracts for the owned
context: this is not a validator for arbitrary shader pointers or programs.

## API use

After creating an active scope, enabling its existing materializer and preparing
owned native source/destination templates:

```objc
uint64_t identity = [scope commandIRIdentityForPipeline:consumer error:&error];
KPGPUCommandSelection *plan = [scope
    newGPUStableCommandIRFromBuffer:source sourceRange:sourceRange
    destination:target destinationRange:targetRange
    resources:catalogue records:records recordOffset:recordOffset error:&error];
// Use the registered native source function's public argument encoder.
[args setIndirectCommandBuffer:target atIndex:0];
[args setComputePipelineState:consumer atIndex:1];
// Bind all registered buffers, then validate before producer commit.
BOOL ready = [plan validateCommandIRArgumentBindings:&error];
```

A direct identity query is optional for ordinary encoder use and useful for
receipts. The encoder exports it through the plan's canonical root. The MSL call
sites do not change. `identity` must not be substituted for a native resource ID
outside this explicitly selected compiler/runtime contract. Old AIR/NAK producers
use the original constructor and positional context instead.

## GPU qualification

The final complete archive is
`4138fb33630e6acad2280858bf993d4d136176b8f34831e30785d5291abdbf59`.
Six objects are identical to the preceding function-encoder archive; only
`KeplerCPUICB.o` changes. Reference: macOS 26.7.1 / 25G241, SDK 26.2,
clang 17, x86_64, PCI `10de:1198`, exact driver profile `e240d54a…`.
[Machine-readable results](stable-pipeline-identity-validation.json).

| Cohort | Signed processes | Independent evidence |
| --- | ---: | --- |
| Native stable-ID dataflow | 18 | 5,950,464 exact consumer uint32 results; 1,487,616 consumer invocations; 93,456,384 guard bytes; eight plan API refusals |
| Previous NAK references | 6 | 1,373,184 results per three-host route; 48 raw stage/counter matches per route |
| Original positional record probes | 3 | 69 cases; 46 dispatches; 141,312 record bytes and 105,984 guard bytes |
| Stable-ID record probes | 3 | 63 cases; 42 dispatches; 16,128 record bytes, 16,128 guard bytes and 46,368 context/guard bytes; nine identity API refusals |
| Native factory/registration contracts | 2 | 50 checks including 30 expected refusals and six native pipeline factory variants per host; zero dispatch |

All 32 hosts are terminal and nonoverlapping. Seventy-two complete 480-byte
contexts and their template permutations are compared after GPU execution.
The dataflow covers four element counts through 32,768, groups including
33/1,024 threads, missing-stage/producer/consumer controls, malformed fields,
separate producer command buffers and encoder reuse. Expected answers are not
uploaded; there are no intermediate CPU record reads or waits between producer,
materializer and consumers. Initial preparation still uses waits.

The duplicate-template process gives each of three pipelines two templates with
the same parameter binding but different local sizes. GPU command setters choose
the appropriate template in all four trials: 457,728 checked results. Six of the
12 executed descriptions select a different template from the CPU root's logged
representative. A root representative is bookkeeping, not a CPU execution choice.
This checks the public encoder's newly admitted identical stable-root case as
well as the GPU refinement and unchanged materializer.

The inert-record probe checks setter ordering, different parameter bindings,
local/grid/shared fields, first-match behavior, copy/reset, incomplete and
nonuniform descriptions, range/version/count refusals and omission controls.
Each process obtains a real ID from one scope, restores it, opens another scope
and checks its new IDs. Two dispatched hosts reject that old ID on the GPU;
the no-dispatch host leaves every record byte unchanged. The raw complete
contexts and both guard regions are verified independently. These record-only
cases never submit their generated descriptions as GPU commands.

A separate native-only build has no archived SM30 programs or NAK executables.
Its two additional hosts pass 457,728 duplicate-template consumer results and
21 stable-record cases, respectively. These counts are outside the final matrix.
All 122 CPU tests pass, along with a C11 ABI layout compilation. All 87 system
references remain unchanged. No new M1 or
performance benchmark was run. Full graphics/FP64/CAS reception suites were NOT
RUN on this new archive; their historical evidence remains separately scoped.

The default-shared counterfactual uses the unchanged record kernel with one
older resolver predicate. It selects candidate 0 instead of the required
zero-shared candidate 3 in case 20: one changed byte in the complete record.
The other 20 cases and every context/guard match their expected before state.
The corrected source always compares requested/default shared bytes; both final
dispatched hosts pass all 21 cases. This repairs our new resolver, not a defect
in the installed NVIDIA compiler. These are inert-record controls.

A preliminary archive passed 31 hosts before the public encoder's duplicate-root
admission was added. Those results and an intermediate 32-host cohort before the default-shared fix
are retained and excluded from the final 32-host totals. A final launcher stopped on a pre-existing log filename before
starting its next child; verified completed cases were preserved and the remaining
cases used a fresh log directory. There was no GPU kill/retry or overwritten
failed evidence in this phase.

## Reproduction

Build the complete runtime from text and use a new workspace, the existing shared
GPU reservation root and verified local fixture directory. The optional archived
NAK references are omitted by default and never needed by the native producers.

```sh
set -e
python3 -B tools/build_from_source.py --out build/stable-identities-local
mkdir "$KP_WORK"
python3 -B bridge/tools/public_native_msl_commands.py build \
  --library build/stable-identities-local --assets "$KP_ASSETS" \
  --function-arguments --stable-identities --nak-baseline --out "$KP_WORK/build"
mkdir "$KP_WORK/accepted"
kp_run() {
  label="$1"; kind="$2"; mode="$3"
  python3 -B bridge/tools/public_native_msl_commands.py run \
    --build "$KP_WORK/build" --out "$KP_WORK/accepted/$label" \
    --reservation-root "$KP_LAB" --kind "$kind" --mode "$mode"
}
kp_run stable-records-execute-0 stable_records execute
kp_run stable-records-execute-1 stable_records execute
kp_run stable-records-no_dispatch stable_records no_dispatch
kp_run contracts-0 contracts inspect
kp_run contracts-1 contracts inspect
for mode in basic barrier copy no_seed no_gather no_finish split no_producer \
            no_consumer bad_parameters bad_counter bad_pipeline \
            bad_buffer3_flag bad_groups bad_reserved refusals encoder_reuse \
            duplicate_templates; do
  kp_run "native-$mode" dataflow "$mode"
done
for mode in basic barrier copy; do
  kp_run "nak-$mode" nak "$mode"
  kp_run "nak-function-$mode" nak_function "$mode"
done
kp_run records-execute-0 records execute
kp_run records-execute-1 records execute
kp_run records-no_dispatch records no_dispatch
python3 -B bridge/tools/audit_native_msl_commands.py "$KP_WORK/accepted" \
  --function-arguments --stable-identities --out "$KP_WORK/stable-audit.json"
```

Omit `--nak-baseline` for a native-only build. `dataflow`, `contracts`, `records`
and `stable_records` remain available; the full auditor intentionally requires
all reference cases. Inputs, exact fixture hashes, source lowering, signed hosts
and independent raw-output oracles follow the previous
[function-encoder workflow](NATIVE_SOURCE_FUNCTION_ARGUMENTS.md). Never overwrite
or replay an uncertain session. Hardware tests share the common cooperative
reservation, not an exclusive claim over WindowServer's GPU activity.

## Scope still open

This implements stable *pipeline* identities in the project ABI. ICB context
addresses remain plan-owned; they are not stable Apple ICB identities. Native
PSO/ICB `gpuResourceID` behavior, arbitrary shipped metallibs, ordinary-library
automatic registration and transparent existing applications remain separate
integration work. Keep the scope alive through completion; restoration racing
encoding, multi-runtime copies, cross-process IDs and per-pipeline removal are
not qualified. Three-buffer roots and other manifests are not newly GPU-qualified
by this four-buffer dataflow profile. Record-only thread/shared cases do not
establish new materializer execution features. No general GPU concurrency,
complete Metal 3/4 conformance, hardware-video decoding or speedup is claimed.
System drivers, SDK, OCLP, protections and WindowServer stay unchanged.
