# Registered native function pipelines

This extension connects native libraries, functions, argument encoders, public device pipeline factories and native buffer bindings for a bounded producer family. Integration remains **level 2**: an adapted application registers one known library and its six offline-compiled SM30 programs, then uses ordinary Metal calls. Arbitrary application libraries and the installed NVIDIA compiler are not automatically repaired.

## Bootstrap and calls

With an enabled IRv2 scope, validated consumer catalogue and locally regenerated assets:

```objc
// compiledPrograms maps all six qualified source function names to program data.
BOOL registered = [scope registerCommandIRLibraryData:sourceLibrary
    expectedSHA256:sourceSHA carrierData:nativeCarrier
    programsByFunction:compiledPrograms error:&error];
if (!registered) { return; }
id<MTLLibrary> library = [device newLibraryWithURL:sourceLibraryURL error:&error];
id<MTLFunction> function = [library newFunctionWithName:@"encode_dataflow_basic"];
id<MTLComputePipelineState> pipeline =
    [device newComputePipelineStateWithFunction:function error:&error];
id<MTLArgumentEncoder> arguments = [function newArgumentEncoderWithBufferIndex:0];
// Validate the plan, encode the supported fields and declare/retain resources.
// Registration enabled automatic factories on the scope-owned queue.
id<MTLCommandBuffer> cb = [queue commandBuffer];
id<MTLComputeCommandEncoder> encoder = [cb computeCommandEncoder];
[encoder setComputePipelineState:pipeline];
[encoder setBuffer:rootArgumentBuffer offset:0 atIndex:0];
```

The excerpt omits required plan validation, resource declarations, retention and ordering. [The tested reception client](../examples/command_ir_pipeline_contracts.mm), [pipeline helper](../examples/PipelineFactoryReception.inc) and [library/function helper](../examples/LibraryFunctionReception.inc) include those checks and controls. Build definitions are `KP_DATAFLOW_NATIVE=0`, `KP_PUBLIC_ARGUMENT_ENCODER=1`, `KP_FUNCTION_ARGUMENT_ENCODER=1`; the M1 reference uses `KP_DATAFLOW_NATIVE=1`. The example needs regenerated local assets; it is not a clean-checkout GPU bootstrap. Its full CLI prefix is `pipeline:queue:encoder:library:function:mode`; for example `5:1:4:2:6:barrier`. The older two-part prefix still selects the default library/function route. The earlier per-function registration API remains available separately; do not register a producer twice through both interfaces.

## Native library and function factories

One registration snapshots the source, carrier and exact six-program set and prepares six native PSOs before publication. Invalid hashes, missing/extra programs and duplicate registration fail closed. Later matching library lookups reuse these profiles without importing another program. The reception client contains no manual per-function registration or compute-encoder adaptation calls.

The qualified library constructors are `newLibraryWithData:error:`, `newLibraryWithURL:error:` and `newLibraryWithFile:error:`. A matching file/URL is read into an immutable, hash-checked snapshot before native construction. Other library bytes follow the original native path. This is object-local adaptation on the scope's device, not a change to shared driver classes.

The five function selectors are:

- `newFunctionWithName:`
- `newFunctionWithName:constantValues:error:`
- `newFunctionWithDescriptor:error:`
- `newFunctionWithName:constantValues:completionHandler:`
- `newFunctionWithDescriptor:completionHandler:`

Each creates a real native function before attaching its registered profile. Descriptor aliases preserve the native returned name while selecting the program by its source function name. The pinned source declares no function constants; nil, empty and unused constant values retain the native behavior. This does not qualify specialization of declared constants. Nondefault function options and binary archives are refused for the registered producers, including `CompileToBinary`; native factory acceptance alone is insufficient evidence for that feature.

The native library/function layouts remain 64/400 bytes for this exact driver profile. Weak associations allow restoration with live objects, and asynchronous function replies release their temporary scope reference before invoking application callbacks. Native objects and retained PSOs can outlive the scope; future calls then take the restored native path. Pipeline asynchronous scheduling is qualified separately below.

The native unsupported-AIR control runs **before** library registration. After activation, successful lookup of that same pinned source is expected and must not be reported as a broken negative control. The earlier failed preflight logs remain preserved. Unregistered consumer libraries provide a separate passthrough control after activation. See [the library/function validation summary](library-function-validation.json).

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

The current repair supports explicit per-pipeline limits within the qualified producer range of 32–1,024. Selected values 32, 64, 128, 256, 512, 1024 are covered by CPU contracts and GPU dataflow trials. Zero retains the native automatic limit. The original NVIDIA path reported 1,024 regardless of descriptor/shader limits: 72 native-only factory observations reproduced that behavior. The same sources on M1 produced 32 supported states and 40 expected descriptor/attribute mismatch errors. The compiler AIR contains the requested `air.max_work_group_size` metadata.

For approved imported producers only, the repair initializes the existing 64-bit native `maxTotalThreadsPerThreadgroup` field (offset 88, instance size 104). It checks the exact driver profile, class, field type/offset/value and original getter before and after the write. Neither the native getter nor the pipeline class is replaced, and shader optimization is unchanged. Each descriptor state is separate from the registered automatic-limit PSO.

After successful producer registration, newly created command buffers from the scope-owned queue automatically adapt their compute encoders. No manual `adaptComputeEncoder:error:` call is needed on that route. Existing callers can still call it idempotently on an active encoder from the same scope. The adapted encoder checks the local-size product before direct threadgroup, grid-thread and indirect dispatch calls, and refuses excessive, zero or overflowing dimensions without changing the native command cursor. Other queues and command buffers created before activation remain outside this automatic route. The application still owns normal Metal resource, geometry and lifetime responsibilities.

The recorded GPU producer geometries are one-dimensional groups of 32,64,128,256,512,1024. The producer's source returns for every grid index except 0: results validate the command dataflow at those requested geometries, not an independent invocation witness for every lane. Earlier shared-memory/atomic tests remain separate evidence.

Active stage inputs, indirect-command support, added/linked binary functions, non-default call stacks, extra buffer mutability, binary archives and unsupported option bits remain rejected. The installed descriptor object lacks the SDK's `shaderValidation` getter; availability is checked before access. General shader-attribute enforcement for arbitrary application libraries remains open. Apple's [descriptor contract](https://developer.apple.com/documentation/metal/mtlcomputepipelinedescriptor/maxtotalthreadsperthreadgroup) and [pipeline maximum](https://developer.apple.com/documentation/metal/mtlcomputepipelinestate/maxtotalthreadsperthreadgroup) describe the API semantics.

No system driver, framework, OCLP, family flag or WindowServer component changes. Apple ICB identity / `gpuResourceID`, arbitrary-library compilation and transparent ordinary-application integration remain open.

## Evidence and reproduction

The [current thread-limit summary](thread-limit-validation.json) records 43 cohorts / 172 GTX trials: 17,393,664 exact uint32 values, 4,348,416 counted consumer invocations and 221,032,448 guard bytes. Seventy CPU contract cases include ten configured-limit requests, 24 expected factory rejections and 18 encoding cases, with 12 refusals before native command emission. Another 42 cases cover pending asynchronous scope release and lifetime contracts. Twelve same-source native M1 trials have 156 common semantic files matching. The [preceding milestone](pipeline-contract-validation.json) retains its own artifact identities and CAS regression results; those counts do not automatically qualify the current artifact.

- `build_command_ir_runtime_library.py`: fresh six-object lab build; the public `tools/build_from_source.py` builds all seven runtime objects, including program import.
- `build_pipeline_contract_reception_client.py` / `qualify_pipeline_factory_contracts.py`: six factory variants, dataflow and negative-control cohorts, using frozen local prerequisites.
- `build_registered_pipeline_contract_probe.py`: reflection, rejection, callback and scope-lifetime probes. No user kernel is submitted by this probe.
- `build_cas_descriptor_transport_regression.py`: descriptor import followed by legacy CAS construction on the same thread.
- `native_thread_limit_probe.mm` / `prepare_native_thread_limit_reference.py`: native-only compiler/factory controls and source-only M1 observer bundle.
- `ThreadLimitContractCases.inc`: field/getter, callback, per-encoder rejection and pipeline-switch controls.
- `verify_native_thread_limit_delivery.py`: current offline numeric/artifact/lifetime/M1/system-baseline verification. Raw binary inputs remain local.
- `verify_pipeline_contract_delivery.py`: preceding milestone verifier, preserving that artifact's historical checks.

Preserved failures include the initial CB0 lowering mistake, a default-stage-descriptor rejection, an unguarded unavailable getter in a CPU-only probe, and the native smaller-thread-limit discrepancy before this bounded repair. No failed run is converted into a successful qualification. A new artifact does not inherit these results. No performance benchmark was run, and the full hardware/driver objective remains incomplete.

## Ordinary queue and encoder factories

Registration now connects the three public queue factories (`commandBuffer`, `commandBufferWithUnretainedReferences`, `commandBufferWithDescriptor:`) and three compute factories (`computeCommandEncoder`, `computeCommandEncoderWithDispatchType:`, `computeCommandEncoderWithDescriptor:`). Serial/concurrent choices and retained/unretained flags are forwarded unchanged. Public-call coverage is a distinct result from native concurrent GPU execution or performance.

Only the scope-owned queue and its newly created buffers receive private zero-ivar subclasses. Shared native class methods are untouched. Scope associations and buffer tracking are weak. Restoration resets live encoder/buffer/queue classes; an outstanding native factory call that completes after restoration returns native objects. Native queue allocation runs outside the scope lock so a full command-buffer pool cannot hold that lock while it waits.

The legacy explicit adaptation method accepts a second call on the same active encoder. It refuses ended encoders, foreign queues and mismatched contexts. New factory calls can begin a recycled native encoder's new recording. An activation boundary remains: existing buffers are not discovered or globally patched.

IR dataflow still requires retained command buffers under its existing ownership/order checks. Unretained factories are qualified for creation and pre-encode rejection, not GPU IR dataflow. When native Metal uses unretained resources, lifetime remains the application's responsibility, as described by Apple's [retainedReferences contract](https://developer.apple.com/documentation/metal/mtlcommandbuffer/retainedreferences).

See `KeplerAutomaticComputeFactories.inc`, `AutomaticQueueContractCases.inc`, `AutomaticQueueBlockingCase.inc`, `QueueFactoryReception.inc`, `qualify_ordinary_queue_factories.py` and `verify_ordinary_queue_delivery.py`. The generated reception client has zero manual compute-adaptation calls. Its four-part CLI form is `pipelineFactory:queueFactory:encoderFactory:mode`; queue factories 0/1 select plain/retained-descriptor, and encoder factories 0–4 select plain, serial dispatch, concurrent dispatch, serial descriptor and concurrent descriptor. The shorter `pipelineFactory:mode` form keeps both defaults at 0.

This removes a per-encoder integration step for the registered subset. Explicit scope initialization, exact library/program registration, the custom command IR and the remaining Apple ICB identity limitations still apply. Integration remains level 2; arbitrary libraries and ordinary unmodified applications are open work.
