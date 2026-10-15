# Registered native function pipelines

This extension connects native `MTLFunction` argument encoders, public device pipeline factories and native buffer bindings for a bounded producer family. Integration remains **level 2**: an adapted application explicitly registers a known library/function and offline-compiled SM30 program. Arbitrary application libraries and the installed NVIDIA compiler are not automatically repaired.

## Bootstrap and calls

With an enabled IRv2 scope, validated consumer catalogue and locally regenerated assets:

```objc
id<MTLFunction> function = [scope newCommandIRFunctionWithLibraryData:sourceLibrary
    expectedSHA256:sourceSHA functionName:@"encode_dataflow_basic"
    rootBufferIndex:0 error:&error];
BOOL registered = [scope registerCommandIRProducerForFunction:function
    carrierData:nativeCarrier programData:compiledSM30 error:&error];
if (!registered) { return; }
id<MTLComputePipelineState> pipeline =
    [device newComputePipelineStateWithFunction:function error:&error];
id<MTLArgumentEncoder> arguments = [function newArgumentEncoderWithBufferIndex:0];
// Validate the plan, encode the supported fields and declare/retain resources.
[encoder setComputePipelineState:pipeline];
[encoder setBuffer:rootArgumentBuffer offset:0 atIndex:0];
```

The excerpt omits required plan validation, resource declarations, retention and ordering. [The tested reception client](../examples/command_ir_pipeline_contracts.mm) and [factory helper](../examples/PipelineFactoryReception.inc) include those checks and controls. Build definitions are `KP_DATAFLOW_NATIVE=0`, `KP_PUBLIC_ARGUMENT_ENCODER=1`, `KP_FUNCTION_ARGUMENT_ENCODER=1`; the M1 reference uses `KP_DATAFLOW_NATIVE=1`. The example needs regenerated local assets; it is not a clean-checkout GPU bootstrap. Its CLI prefix selects `0:basic` through `5:basic` (factory kind followed by semantic mode).

## Supported factory subset

| Kind | Public selector |
| --- | --- |
| 0 | `newComputePipelineStateWithFunction:error:` |
| 1 | `newComputePipelineStateWithFunction:options:reflection:error:` |
| 2 | `newComputePipelineStateWithDescriptor:options:reflection:error:` |
| 3 | `newComputePipelineStateWithFunction:completionHandler:` |
| 4 | `newComputePipelineStateWithFunction:options:completionHandler:` |
| 5 | `newComputePipelineStateWithDescriptor:options:completionHandler:` |

- Exact source library, six function names, carrier and program hashes are pinned. Mutation, mismatches and duplicate registration are refused before import. Unregistered functions use their original native path.
- Returned pipeline states are real native NVIDIA objects. Function variants use the registered PSO; descriptor variants create a distinct PSO through the native constructor and preserve the supported descriptor properties.
- Options 0–3 are qualified. Requested reflection is a fresh `KPIRComputeReflection` adapter, wrapping the real native root argument/type metadata and `MTLBufferBinding` views. It is not the driver's internal reflection class. The qualified root is a dense 48-byte `{ICB,pipeline,4 pointers}` layout.
- Asynchronous callbacks occur once off the requesting thread. Descriptor inputs are copied before return. A queued descriptor request completes after its scope is restored and released; reflection does not retain that scope.
- The producer reads the root pointer from native CB1 offset8, local dimensions from offset0x6f0, and grid dimensions from offset0x720. Full native resource descriptors are retained. No application-built push buffer is uploaded.

## Descriptor limits

Qualified descriptor requests use automatic `maxTotalThreadsPerThreadgroup = 0`, a copied label, an empty stage-input descriptor and the supported execution-width hint. The native constructor returned a PSO maximum of 1,024 even when explicitly asked for 32. The adapter therefore refuses that smaller limit rather than claiming it was enforced. Apple's [descriptor contract](https://developer.apple.com/documentation/metal/mtlcomputepipelinedescriptor/maxtotalthreadsperthreadgroup) and [pipeline maximum](https://developer.apple.com/documentation/metal/mtlcomputepipelinestate/maxtotalthreadsperthreadgroup) describe the distinction.

Active stage inputs, indirect-command support, added/linked binary functions, non-default call stacks, extra buffer mutability, binary archives, unsupported option bits and other unqualified non-default fields are rejected. The installed descriptor object lacks the SDK's `shaderValidation` getter; availability is checked before access. This bounded adapter does not implement every modern descriptor property.

Producer dispatch qualification uses one group of 32 threads; consumer workloads have their separately described geometries. A native PSO reporting 1,024 does not qualify arbitrary producer geometry. Restore removes the scoped adaptation. An invalidated experimental plan must not be reused.

No system driver, framework, OCLP, family flag or WindowServer component changes. Apple ICB identity / `gpuResourceID`, arbitrary-library compilation and transparent ordinary-application integration remain open.

## Evidence and reproduction

The [current summary](pipeline-contract-validation.json) records library/source/client hashes and bounded results: 32 cohorts / 128 GTX trials, 12,358,656 exact uint32 values, 3,089,664 counted consumer invocations, 165,449,536 guard bytes, 17 supported CPU variants, 24 expected rejections, one pending-scope case and 12 native M1 trials with 156 common semantic files matching. The changed descriptor import transport also passed a same-thread legacy CAS regression: 106,650 operations / 90 submissions, with eight expected pin/import rejections.

- `build_command_ir_runtime_library.py`: fresh six-object lab build; the public `tools/build_from_source.py` builds all seven runtime objects, including program import.
- `build_pipeline_contract_reception_client.py` / `qualify_pipeline_factory_contracts.py`: six factory variants, dataflow and negative-control cohorts, using frozen local prerequisites.
- `build_registered_pipeline_contract_probe.py`: reflection, rejection, callback and scope-lifetime probes. No user kernel is submitted by this probe.
- `build_cas_descriptor_transport_regression.py`: descriptor import followed by legacy CAS construction on the same thread.
- `verify_pipeline_contract_delivery.py`: offline numerical, artifact, lifetime, M1 and system-baseline verification. Its raw binary inputs remain local.

Preserved failures include the initial CB0 lowering mistake, a default-stage-descriptor rejection, an unguarded unavailable getter in a CPU-only probe, and the native smaller-thread-limit discrepancy. No failed run is converted into a successful qualification. A new artifact does not inherit these results. No performance benchmark was run, and the full hardware/driver objective remains incomplete.
