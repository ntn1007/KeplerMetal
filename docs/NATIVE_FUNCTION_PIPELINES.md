# Registered native function pipelines

This extension connects the native `MTLFunction` argument encoder, the ordinary synchronous device pipeline call, and native buffer binding for a bounded producer family. It remains integration **level 2**, with explicit registration of a known source and an offline-compiled program. It does not repair the installed NVIDIA compiler or compile arbitrary new MSL automatically.

## Bootstrap and public calls

With a previously enabled IRv2 scope, consumer catalogue and validated artifacts:

```objc
id<MTLFunction>function = [scope newCommandIRFunctionWithLibraryData:sourceLibrary
    expectedSHA256:sourceSHA functionName:@"encode_dataflow_basic"
    rootBufferIndex:0 error:&error];

BOOL registered = [scope registerCommandIRProducerForFunction:function
    carrierData:nativeCarrier programData:compiledSM30 error:&error];
if (!registered) { return; } // preserve error; do not dispatch

id<MTLComputePipelineState>pipeline =
    [device newComputePipelineStateWithFunction:function error:&error];
id<MTLArgumentEncoder>arguments = [function newArgumentEncoderWithBufferIndex:0];
// Encode the supported ICB/pipeline/buffer fields and validate the plan.
// The argument table is the buffer at slot0; no custom Push struct is uploaded.
[encoder setComputePipelineState:pipeline];
[encoder setBuffer:rootArgumentBuffer offset:0 atIndex:0];
```

The excerpt omits required resource declarations, plan validation, retention and command ordering. The [full tested client source](../examples/command_ir_native_pipeline.mm) includes these checks and the CPU/native controls. It requires regenerated local assets and compiler definitions `KP_DATAFLOW_NATIVE=0`, `KP_PUBLIC_ARGUMENT_ENCODER=1`, and `KP_FUNCTION_ARGUMENT_ENCODER=1`; its M1 reference uses `KP_DATAFLOW_NATIVE=1`. It is not a second automatic clean-checkout bootstrap.

## Contract

- Exact source library, six function names, carrier and SM30 program hashes are pinned in the runtime. A mutated carrier, mutated program, program/function mismatch or duplicate registration is refused before import.
- The factory returns a real `NVMTLComputePipelineState`; repeated calls return the registered native PSO. Unregistered ordinary kernels continue through the original factory.
- Native function reflection describes the dense `{ICB,pipeline,4 pointers}` argument table. The native-resource program loads its root pointer from CB1 offset8, local dimensions from CB1 offset0x6f0 and grid dimensions from CB1 offset0x720. The complete driver-managed resource descriptors are preserved.
- The synchronous `newComputePipelineStateWithFunction:error:` selector is extended. Descriptor/options/reflection/asynchronous pipeline creation is **not extended** by this milestone. They follow the native path and may report the original compiler limitation.
- Producer tests dispatch one group of 32 threads. Consumer workloads cover their independently described local sizes, including 33 and 1,024 threads. This does not qualify arbitrary producer geometry.
- Restore removes the function/device adaptation. Tests hold a native function and PSO beyond scope release, verify the scope is released, and confirm that an unregistered/restored function again returns the original native compiler error. Do not use an invalidated experimental plan after restoration.
- No installed driver, OCLP, GPU family/version flag or WindowServer component changes. Native Apple ICB identity / `gpuResourceID` support remains open.

## Reproduction layers

1. `bridge/tools/build_native_resource_command_frontend.py` rebuilds the small AIR harness/front end against the pinned, already-built Mesa libraries. It does not rebuild Mesa or access a GPU.
2. `bridge/tools/build_native_root_command_client.py` preserves an explicit-import control while removing the extra host push buffer.
3. `bridge/tools/build_native_pipeline_command_client.py` uses scoped registration and the public pipeline factory, with mutation/duplicate/unregistered/restoration controls.
4. `bridge/tools/build_native_pipeline_registration_probe.py` checks CPU-side metadata and ownership, retaining a native PSO beyond its scope. No user kernel or command buffer is submitted by that probe.
5. `bridge/tools/verify_native_pipeline_delivery.py` independently recomputes numeric results, validates factory evidence, compares M1 semantic files and rehashes the system baseline. Its inputs are local evidence directories, intentionally omitted from this source repository.

The initial experimental lowering incorrectly read launch dimensions from CB0. All four process trials ended normally but numerical output failed; that result remains preserved locally. The corrected lowering uses CB1 and passed the complete selected suite. This was a defect in the new experimental lowering, not evidence of a hardware limitation.

The [validation summary](native-pipeline-validation.json) reports 64 final GTX trials, 64 producer-registration refusals across those cohorts, 84 argument rejections, 38 metadata/lifetime checks across four trials, and 156 common semantic files matching 12 M1 trials. No performance benchmark was run, and the full hardware/driver objective remains incomplete.
