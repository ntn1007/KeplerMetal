# Local memory and register spills

This milestone qualifies the existing native private-memory path and extends our SM30 import transport to use it. It adds no device family, installed driver or general Metal version support. The API is explicit and restricted to the recorded carrier profiles.

## Distinct evidence

MSL `thread` arrays, NIR scratch and SM30 `l[]` accesses describe per-thread private storage. They are separate from the previously qualified 48 KiB of shared/threadgroup memory. A source array alone does not prove local instructions or allocation, and register pressure alone does not prove spilling.

The native reference uses dynamically indexed volatile private arrays. Its pressure family uses named scalar values loaded before a device barrier and consumed after a volatile key load. Compiler output and disassembly establish native local accesses and 24/224-byte spill frames. NAK reports actual spill/fill operations and nonzero scratch for its pressure cases. Numerical dispatch/readback checks establish execution separately.

| Program | Native frame bytes/thread | NAK scratch bytes | NAK spills/fills |
| --- | ---: | ---: | ---: |
| control | 0 | 0 | 0/0 |
| local32 | 128 | 128 | 0/0 |
| local256 | 1,024 | 1,024 | 0/0 |
| local1024 | 4,096 | 4,096 | 0/0 |
| pressure32 | 0 | 0 | 0/0 |
| pressure64 | 24 | 28 | 7/7 |
| pressure96 | 224 | 156 | 39/39 |
| pressure32, forced spill | reference pressure carrier | 80 | 20/20 |

The last case uses `NAK_DEBUG=spill`: 18 actual registers, with the import allocation padded to the established minimum of 24. No occupancy or speed improvement is inferred. Pressure imports use the compatible 224-byte native `pressure96` carrier; the 24-byte native pressure64 frame cannot hold 28 scratch bytes.

## Import contract

`KPCreateLocalMemoryPipeline` is declared in `KeplerProgramImport.h` and implemented by the shared MRC transport in `KeplerNativeCAS.mm`. Link the complete `libKeplerMetal.a`; the legacy standalone `KeplerProgramImport.mm` implementation does not provide this new entry point. Existing `KeplerImportConfig` remains three uint32 values (12 bytes), and existing entry points keep their behavior.

```objc
KeplerLocalMemoryConfig allocation = {
    63,  // allocated registers
    156, // truthful scratch requirement from this compiled program
    224, // observed compatible native carrier capacity
    224, // native carrier spill metadata
    1    // observed carrier control-barrier profile
};
id<MTLComputePipelineState> pipeline = KPCreateLocalMemoryPipeline(
    device, carrierLibraryData, @"pressure96", compiledSM30,
    allocation, &error, &evidence);
```

The exact driver and carrier library hashes and function/frame profiles are pinned. Inputs are copied; bad profiles, capacities and code shapes are refused. The caller must provide truthful compiler requirements and match the three-buffer ABI: input at index0, uint4 output at index1, and the 16-byte constant parameter block at index2. This API does not validate arbitrary machine-code safety. External CRS requirements remain unsupported.

In the qualified native containers, metadata words12/13 equal the private frame size; word14 records the native spill size, and word9 follows 64×frame bytes. The new path preserves those local-allocation fields and other metadata, updates word0 to `code_bytes/8 - 1` and word7 to the allocated GPR count, and requests the previously qualified structured-control word11=576. The complete meaning of this opaque control field is unresolved. For these pinned tuples its addition increases the decoded allocation word at variant offset40 by 1,024; this is checked before dispatch, along with decoded code length, GPRs, instruction count and native spill metadata. These observations are not a universal NVIDIA ABI.

The guarded control initially imported with word11=0 but wrote no results. A branchless diagnostic passed. The guarded program was retained for final qualification and passes with the control reserve; its machine-code hash matches the failing program. CPU-only guard refusals and failed GPU results were preserved. Unsupported data is never reclassified as a successful import.

## Qualification

The final cohort has 180 compute trials and 48 missing-dispatch controls, including group sizes 1,31,32,33,64,128,256,512,1024 and selected multiple groups. All launches contain complete, in-bounds threadgroups; this includes partial warps but does not qualify nonuniform threadgroups. The pressure kernels contain a workgroup barrier.

An independent integer CPU oracle checks all output bytes and input buffers, plus guards. Each invocation writes a varying four-word witness/checksum. This checks kernel results, not every internal scratch byte directly. Native and imported kernels have matching semantics; missing dispatch leaves the expected answers absent. Caller-owned carrier/code copies are wiped before commit in imported cases. Constructors are restored, and local→descriptor→CAS execution in one process verifies context cleanup. The full hardware objective remains open. See [the exact artifact summary](local-memory-validation.json).

## Native reference from a source checkout

On the qualified iMac, with Xcode and its Metal tools selected:

```sh
mkdir -p bridge/results
python3 bridge/tools/build_local_memory_probe.py --out bridge/results/local-native-build
python3 bridge/tools/run_command_ir_runtime.py --build bridge/results/local-native-build --out bridge/results/local-native-run --mode local1024
python3 bridge/tools/verify_local_memory.py bridge/results/local-native-run
```

This compiles original MSL and an application from text, executes the native driver and checks results. It needs no proprietary binary from the repository. The device/driver profile is strict; other machines need a separately qualified profile. Use new result directories. All runners sharing the GTX must use one designated reservation root. When another checkout already owns the lab root, use its launcher with the new build path rather than starting an independent reservation. The cooperative lease does not exclude WindowServer or arbitrary external GPU applications.

For NAK, obtain/build the open source dependencies in [the dependency guide](DEPENDENCIES.md). The historical lab builder `build_local_memory_programs.py` consumes the existing Mesa build; its manifest fingerprints all linked archives, source inputs and generated programs. The local tree is an extracted Mesa26.2.4 source tree, with no nested Git checkout; the upstream reference commit is documented separately from effective artifact hashes. Run with a known `NAK_DEBUG` environment; the forced-spill case sets it for that child only.

The imported tests intentionally retain a pinned carrier hash. Regenerating a metallib using another SDK or path may change its bytes. A mismatch needs a new profile and native-capacity/import/GPU qualification, rather than changing the allowlist merely to proceed. Generated programs, Metal libraries, raw containers, SDKs and vendor drivers are omitted. The full 19-cohort import suite is a laboratory workflow with frozen prerequisites, not a clean-checkout automatic GPU bootstrap.
