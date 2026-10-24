# GPU-generated commands with native texture arguments

The GTX 880M now has a qualified adapted-client path where a native NVIDIA
producer writes a compute command, selects between two native texture argument
buffers, and passes that record to the existing GPU materializer and resident
command transport. The consumer samples the selected texture and sampler and
reads its selected nested input buffer. Raw records, native binding tables,
descriptors, witnesses and sampled outputs agree with the independent CPU oracle.

This qualifies another composition of the existing runtime. The complete
seven-object archive is unchanged. It is branch B work at integration level 2;
Apple's native ICB object/resource ABI, transparent application support, broader
Metal 3/4 functionality and a replacement system driver remain separate work.
The application still retains samplers and declares/retains indirectly used
textures, parents and buffers. No speedup is claimed.

## What executes

1. NVIDIA's native argument encoder produces two complete 24-byte argument
   buffers, each containing a texture, sampler and nested buffer pointer.
   They are uploaded into two separate owned Private buffers at offset 64.
   The alternate bank switches the texture/mip view, sampler addressing and
   nested input. No opaque texture/sampler encoding is fabricated.
2. One immutable source-library registration enables ordinary URL-library,
   named-function and synchronous pipeline creation for the producer. Its
   public function argument encoder uses the existing dense 40-byte project
   root: context, pipeline identity and three buffer pointers.
3. The producer calculates `(count ^ seed ^ trial) & 1` on the GPU and writes
   a 128-byte command record with that bank's argument-buffer address. The
   initial producer root always points to bank 0; a resolved choice is never
   supplied by the CPU. The alternate owned buffer's public GPU address is
   fixture metadata in parameter words 4–5. The normal consumer reads only
   parameter words 0–3. Both choices belong to the sealed resource catalogue.
4. The unchanged v2 materializer validates that record and copies the full
   native binding descriptors into CB1 on the GPU. The CPU submits the existing
   resident launch packet; it does not upload the selected QMD or CB1 state at
   launch. The GPU-produced descriptor carries the actual group count.
5. The native texture consumer executes. Only after it completes are records,
   CB1, QMD, context, counters and outputs read back for verification.

The three trials have 16, 65 and 257 active invocations, with groups of 32
threads. The calculated banks are 0, 1 and 1. The oracle checks that the
recorded address, native CB1 address, materializer witness and resulting pixels
all identify the selected bank, while the producer root still names bank 0.
It also checks mip-view dimensions, the original native encodings, both Private
argument-buffer readbacks, inputs, constants and all explicitly initialized
guards. Readback has no role in choosing or submitting the commands.

The source uses the explicit workspace `metal_command_buffer` replacement
header, not Apple's unsupported `air.command_buffer` ABI. The SDK is unchanged.
The 40-byte root and stable pipeline token are KeplerMetal contracts, not native
Apple resource IDs or support for arbitrary unmodified shader libraries.

## Controls and qualification

Six modes run in three fresh-process series: the baseline GPU mode, changed
texture, changed sampler, changed nested buffer, no producer and no consumer.
The `wrong_*` names denote valid alternative resources with different expected
pixels, not invalid resources submitted to the display GPU.

Without a producer, the record remains zero. The materializer reports invalid
status 2 and writes a zero-CTA descriptor; the encoded consumer makes no texture
invocations. Without a consumer, records and descriptors remain valid but every
output stays at its sentinel. These are passing controlled cases, not ignored
infrastructure failures. The ordinary native argument-encoder getter is queried
again after scope restoration and must return `NVMTLIndirectArgumentEncoder`.

The final reception contains 18 new GPU-command hosts and 10 fresh direct/CPU-ICB
regression hosts. The compact [receipt](gpu-icb-texture-validation.json) separates
GPU-computed output values from no-dispatch sentinel checks and warm preparation.
Only nonzero consumer workloads count as texture dispatches; the no-producer
resident launch calls are listed separately through their zero-CTA records.

The new GPU path executes 36 nonzero texture-consumer dispatches, 45 producer
and 54 materializer dispatches. Its independent oracle checks 16,224 computed
uint32 values, 8,112 sentinel words, 111,024 guard bytes, 45 populated records
and nine zero-CTA records. The fresh regression adds 24 texture dispatches,
10,816 computed values, 2,704 sentinel words and 38,880 guard bytes. All 228 raw
file pairs agree; all 159 CPU tests pass. The 87 monitored system files are
unchanged. Five preliminary signed hosts are separate from these 28 final hosts.

A fresh build using the reconstructed public-source auxiliary shaders produces
exactly the same application, shader assets, frozen source, oracles and runners
as the final GPU qualification. No additional GPU run is claimed for that
byte-identical rebuild.

The runtime remains the complete seven-object archive with SHA-256
`875cb4b9f3e30022b110709b0bd9c7fe6c0efcb58ddc19eccedbec6543c52551`.
The exact installed GeForceMTLDriver is
`e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645`.
The consumer is the unchanged native shader from the preceding
[CPU-encoded ICB qualification](ICB_TEXTURE_ARGUMENTS.md). Unknown profiles
remain refused; no gate or manifest pin was relaxed.

## Source-only reproduction

Requires the documented Intel/macOS toolchain: macOS 26.7.1/build 25G241,
SDK 26.2, clang 17.0.0/clang-1700.6.4.2 and Metal 32023.864. Existing working
Kepler drivers are obtained separately; see [dependencies](DEPENDENCIES.md).
All commands below write fresh workspace output directories. Every Metal host
uses an immutable signed copy and the existing common lab reservation root.
Build and audit commands submit no GPU work.

```sh
python3 tools/build_from_source.py --out "$LIB"
python3 bridge/tools/build_gpu_icb_texture_assets.py --out "$COMMAND_ASSETS"
python3 bridge/tools/public_gpu_icb_texture.py build --library "$LIB" \
  --command-assets "$COMMAND_ASSETS" --out "$GPU_BUILD"
python3 bridge/tools/public_icb_texture.py build --library "$LIB" --out "$BASE_BUILD"

mkdir "$COHORT" "$COHORT/baseline"
for mode in native native_wrong_texture native_wrong_sampler native_wrong_buffer native_no_dispatch cpu cpu_wrong_texture cpu_wrong_sampler cpu_wrong_buffer cpu_no_dispatch; do
  python3 bridge/tools/public_icb_texture.py run --build "$BASE_BUILD" \
    --mode "$mode" --out "$COHORT/baseline/$mode" \
    --reservation-root "$RESERVATION_ROOT" || exit 1
done
for repeat in 0 1 2; do
  mkdir "$COHORT/gpu-$repeat"
  for mode in gpu gpu_wrong_texture gpu_wrong_sampler gpu_wrong_buffer gpu_no_producer gpu_no_consumer; do
    python3 bridge/tools/public_gpu_icb_texture.py run --build "$GPU_BUILD" \
      --mode "$mode" --out "$COHORT/gpu-$repeat/$mode" \
      --reservation-root "$RESERVATION_ROOT" || exit 1
  done
done
python3 bridge/tools/audit_gpu_icb_texture.py "$COHORT" \
  --reference "$PRECEDING_TEXTURE_COHORT" --out "$NEW_RECEIPT"
python3 -m unittest discover -s tests
python3 tools/check_publication.py
```

`PRECEDING_TEXTURE_COHORT` is the independently produced preceding three-series
texture cohort, with `repeat-0/<mode>/outputs` as documented in
[ICB_TEXTURE_ARGUMENTS.md](ICB_TEXTURE_ARGUMENTS.md). The auditor compares 120
fresh baseline files with it, then 108 output/input files across the new GPU
repetitions. Address-dependent records/parameters are validated structurally
within each process, not compared byte-for-byte across process allocations.

The four command shaders rebuild from the existing public MSL sources with
their original pins. The v2 materializer retains its historical compiler input
basename. No archived compiled fixture, NAK program or proprietary driver is
distributed or downloaded for this reproduction. A changed compiler output
fails the pin check and needs separate qualification.

## Limits and next scope

The descriptor catalogue remains sealed and bounded, with the existing serial
transport and its stronger WAIT_FOR_IDLE ordering. This tests two native
RGBA8Unorm argument banks, nearest clamp/repeat sampling, a restricted mip view,
three buffer slots and one generated command. It is not a qualification of
other formats, filtered sampling, table growth, concurrent execution, other
profiles, native Apple ICB identities or automatic resource-lifetime handling.
Nonzero CB2 offsets retain the separate limitation recorded in the preceding
milestone. CAS, FP64, render and video reception are historical, not rerun here.

Further work should expand the supported command/resource contracts and
graphics integration while preserving these independent records, descriptor
and numerical checks. System-wide driver integration and hardware video still
require their own evidence and authorization before any system deployment.
