# Native source producers through public function argument encoders

The source-lowered command producer can now use its real native `MTLFunction`
argument-encoder getters to bind the prepared ICB, registered consumer pipeline
and retained buffers. It no longer needs the client to copy canonical root
addresses or encode catalogue tokens manually. The producer is still compiled
by the installed NVIDIA backend; its ordinary pipeline factories stay native.
This extends adapted-client integration with CommandIR v2. It is not Apple's
opaque ICB representation, stable `gpuResourceID` support or a system update.

## Contract

`newNativeSourceCommandIRFunctionWithLibraryData:expectedSHA256:functionName:rootBufferIndex:error:`
returns a real native function from an immutable, digest-checked library snapshot.
It requires an active IRv2 scope and root buffer 0. The caller explicitly selects
the source-lowered ABI and remains responsible for the shader's semantics;
registration is not a validator for arbitrary shader programs.

Native reflection must describe a dense, aligned root with either three or four
buffer pointers after a context pointer and a 64-bit pipeline token. The context
pointer must reference the complete 32-byte `KPCommandContext` layout: seven
named fields with exact offsets/types, read-write access and eight-byte alignment.
The tested end-to-end profile has four buffers and a 48-byte root. Three-buffer
root acceptance is a structural contract, not new GPU qualification here.
A context with a signed address, extra field or readonly access is refused.
Ordinary Apple ICB/pipeline root metadata is refused by this constructor; the
older constructor independently refuses the lowered root. Neither representation
is inferred from an arbitrary pointer-sized value.

Only the function's two argument-encoder getters are adapted. Their reflection
variant returns the unchanged native pointer/scalar metadata. The returned
encoder implements public ICB, pipeline and buffer binding selectors using the
existing retained, sealed resource catalogue. After all bindings, call
`validateCommandIRArgumentBindings:` **before any producer commit**. The plan
validates complete roots, disjoint spans, registered resources and ownership;
changing root bytes after validation violates the cooperative immutable-input
contract. This does not protect against an application deliberately rewriting
its own buffers after submission.

The normal NVIDIA function/descriptor, synchronous/asynchronous pipeline
constructors compile this native function without the imported-producer factory.
No cached imported producer PSO or private instruction replacement is installed
by the new registration. Reflection on a pipeline stays native. A scope can own
old opaque-root and new lowered-root function instances at the same time: the
ABI selection belongs to each function association, not its shared subclass.
Restoration reinstates both native getter implementations. An encoder retained
after restoration refuses further use.

The existing argument encoder holds the scope and active plan; a plan retains
its context, buffers, pipeline catalogue and exported roots. Setting a fresh
argument-buffer destination detaches the prior plan from the encoder while the
prior submission's completion ownership remains intact. The GPU cohort exercises
one encoder reused across four completed plans and checks weak lifetimes.
It does not qualify concurrent encoding, reuse of an in-flight target or
restoration racing another thread's argument binding.

## Qualification on the GTX 880M

Reference: macOS 26.7.1 / 25G241, SDK 26.2, clang 17, x86_64,
PCI `10de:1198`, exact installed driver profile `e240d54a…`.
The new complete seven-object archive is
`dc86b1b955326bacbf82cd324575b56950ef1cc90234cb84db910b100dc25fa4`.
Six objects are byte-identical to the previous qualified archive; only
`KeplerCPUICB.o` changes. This does not attribute earlier complete graphics,
FP64 or CAS reception suites to the new archive; those suites were NOT RUN here.
[Machine-readable evidence](native-source-function-validation.json).

| Cohort | Processes | Independent checks |
| --- | ---: | --- |
| Native producer with function encoders | 17 | 5,492,736 exact consumer uint32 results; 1,373,184 active consumer invocations; 86,526,496 guard bytes; eight plan API refusals |
| Previous direct-root NAK reference | 3 | 1,373,184 exact results; 48 complete stage/counter files identical to native |
| Previous function-encoder NAK reference | 3 | 1,373,184 exact results; another 48 complete stage/counter files identical to native |
| Record generation/omission controls | 3 | 69 cases, 46 dispatches; 141,312 record bytes and 105,984 guard bytes |
| Registration/factory/coexistence contracts | 2 | 50 checks, including 30 expected refusals and all six native factory variants in each process; zero dispatch |

All 28 signed hosts are terminal and nonoverlapping. The native matrix covers
all six producer functions, four element counts (256, 1,024, 4,096, 32,768),
33/1,024-thread groups, split command buffers, absent stages/producers/consumers,
malformed fields and encoder reuse across four completed plans. Full native
constant-binding images and materializer witnesses are checked alongside data
and guards. No expected output values are uploaded; there are no intermediate
CPU waits or command-record readback between producer and consumers. Preparation
waits remain separate from this property.

A separate native-only build contains no archived SM30 programs or NAK client.
Its two additional terminal hosts pass 457,728 consumer uint32 checks and another
25 registration/factory/coexistence checks, respectively. These are separate
from the 28-process totals. All 117 CPU tests pass, and the 87 system references
remain unchanged. No M1 or performance run was performed.

The initial pilot's GPU results were correct, but its verifier expected four
function getters and omitted the initial stride-check getter. That frozen
failure is retained; a separate corrected re-audit checks all 457,728 results.
The final cohort uses the corrected oracle and accounts for five getters,
or two when one encoder serves all four plans. An intermediate contract-host
compile failure from two missing token separators is also retained; it involved
no GPU execution. Final contract controls include both root ABI directions,
malformed context types/sizes/access, immutable caller inputs, same-process old
and new functions, native reflection/factories and restoration/inactive handles.

## Source usage

Build the producer with the workspace-only lowering described in
[NATIVE_MSL_COMMANDS.md](NATIVE_MSL_COMMANDS.md). After scope/materializer setup:

```objc
id<MTLFunction> producer = [scope
    newNativeSourceCommandIRFunctionWithLibraryData:producerLibraryBytes
    expectedSHA256:producerLibraryDigest
    functionName:@"encode_dataflow_basic"
    rootBufferIndex:0 error:&error];
id<MTLComputePipelineState> writer =
    [device newComputePipelineStateWithFunction:producer error:&error];
id<MTLArgumentEncoder> args =
    [producer newArgumentEncoderWithBufferIndex:0];
[args setArgumentBuffer:root offset:0];
[args setIndirectCommandBuffer:preparedTarget atIndex:0];
[args setComputePipelineState:registeredConsumer atIndex:1];
// Bind all four registered buffers at indices 2...5 with their catalogue offsets.
// Validate the complete plan before committing the producer.
```

The reception client is `bridge/tools/command_ir_dataflow_client.mm` with
`KP_NATIVE_MSL_COMMANDS`, `KP_PUBLIC_ARGUMENT_ENCODER` and
`KP_FUNCTION_ARGUMENT_ENCODER` enabled. Its normal selectors bind four buffer
slots, scalar/array forms and three root-array elements. Unsupported operations
remain bounded by the existing encoder rather than being silently forwarded.

## Reproduction

Use new output directories, the existing common physical-GPU reservation root,
and the locally verified fixture directory described in the earlier native
producer workflow. Never run a second cohort concurrently. The optional NAK
baseline needs its previously generated programs; the default native-only build
does not. `KP_WORK`, `KP_ASSETS` and `KP_LAB` are caller-selected paths.

```sh
set -e
python3 -B tools/build_from_source.py --out build/native-function-local
mkdir "$KP_WORK"
python3 -B bridge/tools/public_native_msl_commands.py build \
  --library build/native-function-local --assets "$KP_ASSETS" \
  --function-arguments --nak-baseline --out "$KP_WORK/build"
mkdir "$KP_WORK/accepted"
kp_run() {
  label="$1"; kind="$2"; mode="$3"
  python3 -B bridge/tools/public_native_msl_commands.py run \
    --build "$KP_WORK/build" --out "$KP_WORK/accepted/$label" \
    --reservation-root "$KP_LAB" --kind "$kind" --mode "$mode"
}
kp_run contracts-0 contracts inspect
kp_run contracts-1 contracts inspect
for mode in basic barrier copy no_seed no_gather no_finish split no_producer \
            no_consumer bad_parameters bad_counter bad_pipeline \
            bad_buffer3_flag bad_groups bad_reserved refusals encoder_reuse; do
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
  --function-arguments --out "$KP_WORK/native-function-audit.json"
```

Omit `--nak-baseline` for a native-only build with `dataflow`, `records` and
`contracts` executables. The full matrix auditor intentionally requires all
28 processes and both legacy reference routes. The builder freezes its own
source, compiled host/header/kernel sources, local ABI transformations, exact
fixture hashes and independent oracles. Negative reflection fixtures are
compiled normally but never dispatched. The ordinary opaque MSL library is
regenerated from text and checked against the historical pin before use as the
legacy NAK/function baseline.

## Limits and next integration boundary

Function registration remains explicit, and shaders need our opt-in source
lowering. The default mode uses plan-positional pipeline tokens. The subsequent
[stable identity extension](STABLE_PIPELINE_IDENTITIES.md) now resolves scope-owned
pipeline IDs against each plan on the GPU, including duplicate local-size
templates. Those identities are distinct from native PSO/ICB `gpuResourceID`;
ICB context identities and automatic loading of arbitrary shipped metallibs
remain open. Command execution remains serial. Rendering commands, arbitrary root
schemas, strided/remaining constant-space bindings, automatic application-wide
registration and transparent ordinary-application integration remain open.
No performance improvement, complete Metal 3/4 support or hardware-video decoding
is claimed. System drivers, SDK, OCLP, protection and WindowServer stay unchanged.
