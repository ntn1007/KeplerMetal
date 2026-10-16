# Native allocation API in the common runtime

The allocation correction is now an explicit application API in the shared MRC transport. It preserves the NVIDIA-generated GPU program and increases only native metadata words 9/11 for developer-qualified compute profiles. It does not install or replace a driver. This is branch A behavior correction, with application integration level 2.

## Contract

[`KeplerNativeAllocation.h`](../bridge/src/KeplerNativeAllocation.h) exports:

```objc
id<MTLComputePipelineState> KPCreateCertifiedNativeAllocationPipeline(
    id<MTLDevice> device,
    NSData *libraryData, NSString *expectedLibrarySHA256,
    NSData *certificateData, NSString *expectedCertificateSHA256,
    NSError **error, NSDictionary **evidence) NS_RETURNS_RETAINED;
```

The implementation is [`KeplerNativeAllocation.inc`](../bridge/src/KeplerNativeAllocation.inc), included in `KeplerNativeCAS.mm`. ARC clients use the retained C factory annotation; the implementation compiles with MRC. Concrete immutable copies of library and certificate bytes are made before use. A successful pipeline retains the input snapshots and constructor payloads. No external file or sidecar is read by this API.

The JSON certificate binds schema 1, intent `native_control_reservation`, function name, exact library and driver SHA256, native code SHA256/size, all 58 metadata words, and reserve 4096. Boolean and fractional integer fields are refused. Stable metadata words must match; variable words 2/4 are preserved from the actual constructor input. The current bounded profile accepts code up to 104,000 bytes, native frames up to 4,656 bytes,1–63 GPRs, equal frame words 12/13 and a spill field no larger than the frame. Words9/11 may only increase. The decoded allocation, spill field, code size, instruction count and register count are checked after construction. Complete constructor payload and code identity are checked after the original constructor returns.

The target remains the exact GTX 880M device/registry and driver SHA256 `2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054`. A certificate is an artifact pin supplied by the application developer, **not** a signature from a trusted issuer or proof that arbitrary shaders are safe/correct. Qualify each program first. Reserve4096 is a tested setting; a general or minimal allocation rule is not established. Constructor payload identity does not independently read back resident GPU instructions.

Unsupported, mismatched, cached/no-callback or ambiguous cases return nil. A late mismatch passes the untouched native input to the original constructor, restores the method and discards the pipeline. GPU dispatch and correctness are separate from successful construction.

## Serialization and restoration

The new API uses the same `importMutex` as the common CAS, local-memory and descriptor import implementations. Its active context is thread-local. Unrelated native constructor calls on another thread pass through to the original implementation. Nested imports on the same thread are refused before attempting the mutex. The legacy standalone `KeplerProgramImport.mm` implementation has separate interception state: applications must serialize any other constructor interposition explicitly.

A controlled factory-concurrency test exposed a bug in **our CAS adapter**: it sampled the original constructor IMP before acquiring the shared mutex, and could observe the allocation API's valid temporary hook. The subsequent comparison reported a false restoration failure even though the constructor had been restored. The fix records restoration inside the serialized core while the mutex is still held. The failed process exited 3 with zero GPU kernels and is retained; it is not evidence of an NVIDIA driver or GPU failure.

The fixed test proves that a CAS factory waits for the allocation scope and that at least one unrelated native constructor actually passes through during that scope. Three GPU computations then execute serially and match CPU oracles. It does not qualify simultaneous GPU execution or arbitrary third-party interposition.

## Qualification on the lab archive

Archive SHA256 `5636b0d0d158fc985bf9b1df5fd0e16b91909a9a6f48423c175272b7fe4ddb67` was rebuilt from six runtime objects with no reused object. Its qualification comprises:

| Cohort | Result |
| --- | --- |
| Native allocation |228 compute trials,17 distinct native profiles;340,784 exact uint32 results; includes 24 lifetime trials after caller input overwrite and factory-pool drain |
| Missing-dispatch controls |24 submitted command buffers, zero compute dispatches; untouched-output expectation verified |
| API refusals |16 real cases, zero command buffers;11 input/schema refusals, one missing callback, four constructor mismatches; native recovery PSO created after every refusal |
| Controlled factory concurrency |Three serial GPU computations after overlapping factory calls;660 exact uint32 results,99 correct CAS operations |
| Allocation → local → descriptor → CAS |90 CAS submissions /106,650 correct operations, followed by local32 and still-live native96 computations; eight CAS import refusals remain effective |
| Local-memory regressions |36 compute trials:4 KiB private arrays, pressure96 and pressure32 forced spilling;53,808 exact uint32 results |

Total: 383 user command buffers,359 compute dispatches and24 missing-dispatch controls;822,116 exact uint32 results and161,152 guard bytes. The descriptor prelude creates a pipeline; it does not execute a descriptor producer in this cohort. The full historical 296-trial library/function suite was **NOT RUN** on this archive. The 83 tracked system files and OCLP match the initial hashes. No new M1 run or performance benchmark was performed.

The previous standalone experiment and its 48 failing replay/rounding controls remain archived separately. They establish historical causal evidence; their counts are not added to this archive's qualification.

One additional harness failure is retained: an unavailable `pressure96_forced_spill` profile caused a nil-JSON exception before pipeline creation or GPU submission. The existing profiles are `pressure96` and `pressure32_forced_spill`; both pass in the regression cohort.

## Source-only reconstruction and reproduction

The fresh-checkout supported build remains:

```sh
python3 tools/check_publication.py
python3 -m unittest discover -s tests -v
python3 tools/build_from_source.py --out build/source-local
```

It rebuilds seven runtime objects from text and checks whole-archive linking without GPU dispatch. Its archive is different from the six-object laboratory archive and needs artifact-specific qualification. See [the validation summary](native-allocation-runtime-validation.json) for the separate public rebuild results.

These lab builders retain the exact source workflow but require the earlier locally regenerated native libraries, observations, CAS assets and runners; those binaries are intentionally absent from GitHub:

```sh
python3 bridge/tools/build_native_allocation_runtime_probe.py \
  --out bridge/results/allocation-client-new \
  --library build/source-local \
  --native-build bridge/results/control-flow-native-build-20261015-02 \
  --observations bridge/results/control-flow-native-observations-20261015-02 \
  --lifetime
python3 bridge/tools/run_command_ir_runtime.py \
  --build bridge/results/allocation-client-new \
  --out bridge/results/allocation-result-new --mode depth96
```

Use a new directory for each build/result. Review the source and share the original host reservation root with other checkouts before execution; do not run two cohorts concurrently. The API is not enabled for arbitrary public applications. The recorded milestone can be rechecked offline, when its private fixtures are available, with `bridge/tools/verify_native_allocation_runtime.py --out bridge/results/recheck-new.json`; this does not rerun the GPU. Independent factory/coexistence checks are in `verify_native_allocation_common.py`.

The next driver task is a principled allocation rule across more compiler/program profiles, then an explicit decision about broader native factory integration. Video, display, power, sustained/full-VRAM pressure and general Metal 3/4 conformance remain separate open work. No speedup is claimed.
