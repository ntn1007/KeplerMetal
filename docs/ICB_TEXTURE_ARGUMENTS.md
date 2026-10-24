# Native texture arguments through existing compute ICBs

The existing CPU-encoded KeplerMetal compute-command transport now has an
execution test for a native texture/sampler argument buffer. NVIDIA's native
compiler and argument encoder produce the consumer and its complete 24-byte
argument encoding. The runtime itself is unchanged in this milestone.

This is branch B qualification of existing functionality, at adapted-application
integration level 2. The caller still owns and declares every indirect texture,
parent texture and nested buffer, and retains the samplers through completion.
There is no new automatic resource-lifetime API, GPU-generated texture-command
qualification, installed-driver change, general Metal 3/4 support or speedup claim.

## Workload and controls

`bridge/src/icb_indirect_texture.metal` samples RGBA8Unorm textures with a native
sampler, queries width/height/mip count, reads a nested buffer at a nonzero
offset, and writes four integer witnesses per invocation. Each host tests 16,
65 and 257 active invocations, with 32 threads per group and padded allocation
bounds. A new CPU oracle checks the raw outputs rather than trusting the host's
PASS counter.

The native argument buffer contains a texture, a sampler and a buffer pointer.
Its full native encoding is copied at offset 64 into a Private GPU buffer.
Both paths use the same native shader, parameters, input and output guards:

| Mode suffix | Expected behavior |
| --- | --- |
| none | 4×4 texture, nearest sampling, clamp-to-edge |
| `_wrong_texture` | Valid 4×4 mip-level view of a different 8×8 parent; different pixels |
| `_wrong_sampler` | Valid nearest/repeat sampler; different out-of-range samples |
| `_wrong_buffer` | Different nested input buffer; different integer witnesses |
| `_no_dispatch` | No consumer dispatch; every output word stays at its sentinel |

The `wrong_*` labels identify controlled changes from the baseline. They are
valid resources, with independently calculated expected results; no invalid
resource handles or malformed command streams are submitted to the display GPU.

The raw evidence also includes a full readback of the Private argument buffer,
both nested inputs and the constant buffer. The verifier checks complete padded
output guards, both argument-buffer guards, and unchanged constants/inputs.
Direct/ICB comparisons exclude resource addresses, which vary between processes.

## Results

Three fresh-process series and one metadata host passed 31/31 final hosts:

| Observation | Count |
| --- | ---: |
| Native direct hosts / CPU-encoded ICB hosts |15 /15 |
| Actual consumer dispatches |72 |
| Exact computed uint32 results |32,448 |
| Sentinel words in no-dispatch controls |8,112 |
| Unchanged guard bytes |116,640 |
| Byte-identical direct/ICB raw file pairs |180 |
| Of those, output-file pairs |45 |
| CPU unit tests |144 |
| Unchanged system hashes |87 |

Computed values include both execution paths and all three repetitions. The
no-dispatch sentinel checks are separate from GPU-computed values. Raw pairs
include output, parameters and both nested inputs; changing GPU resource
addresses are compared within each process through the argument-buffer readback.
The final ICB trace checks native command copies, actual unsuppressed launches,
zero user invocations during preparation, literal ownership and scope restoration.
See the compact [qualification receipt](icb-texture-validation.json).

The runtime archive is byte-identical to the preceding native-library milestone.
The historical94-host runtime reception was not rerun: this phase adds a shader,
client, profile and validators, with no core runtime edit. The new 31-host matrix
and 144 CPU tests are fresh. No new full CAS, rendering, FP 64, video or M 1-Max
qualification is claimed.

## Exact native profile

Qualification uses macOS 26.7.1/build 25G241, SDK 26.2, the x86_64 GTX 880M/PCI 10de:1198
and the existing complete seven-object runtime:

| Artifact | SHA-256 |
| --- | --- |
| Runtime archive |`875cb4b9f3e30022b110709b0bd9c7fe6c0efcb58ddc19eccedbec6543c52551` |
| Installed GeForceMTLDriver |`e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645` |
| Locally compiled consumer.metallib |`6543a1f560c0dcfe7f1421c20c9e9fc3a5ea911644a6dfd0d14d1f20d5db3e71` |

The metadata probe compiles a native pipeline, encodes an uncommitted dispatch,
reads only its own process's already established ABI fields, and exits without
submitting that command buffer. CPU parsing independently checks nine packets,
a464-byte command,17 registers, zero spill,1216 code bytes, CB-valid mask 7 and
a 256-byte literal bank at the aligned native code end. This is preparation
evidence; the separate numerical hosts supply actual GPU execution evidence.

The manifest registers only the three top-level buffer bindings. It does not
describe or validate arbitrary nested pointers. The caller's explicit resource
ownership and residency declarations remain essential. New resource kinds,
table growth/replacement, concurrent encoders, other hardware and driver/SDK
profiles need their own qualification.

## Preserved allocation refusals

Two preliminary CPU-ICB hosts exited8 during preparation, without executing
the consumer. Both were observed terminal, without a kill request:

1. 512 total constant bytes with binding offset 256 left less than the 512 bytes
required by the current transport.
2. 768 total bytes with binding offset 256 passed that extent check but produced
a native CB2 size of 768, while the transport expected the remaining 512 bytes.

The final client uses the existing qualified constant binding at offset 0 with
512 bytes on both paths. No runtime gate was weakened or CB2 packet rewritten.
Nonzero CB2 offsets remain a separate, demonstrated qualification boundary.
Those pilot failures are preserved outside the final qualification counts.

## Reproduction from public sources

Requires the documented Intel/macOS toolchain and an already functional native
Kepler driver obtained separately; see [dependencies](DEPENDENCIES.md). No
Apple/NVIDIA binary, compiled shader or command capture is distributed here.
Use new output directories. `RESERVATION_ROOT` must be the existing shared lab
reservation root, also used by every other KeplerMetal GPU host on this machine.

```sh
python3 tools/build_from_source.py --out "$LIB"
python3 bridge/tools/public_icb_texture.py build --library "$LIB" --out "$BUILD"

mkdir "$COHORT"
python3 bridge/tools/public_icb_texture.py run --build "$BUILD" \
  --mode metadata --out "$COHORT/metadata" --reservation-root "$RESERVATION_ROOT"

for repeat in 0 1 2; do
  mkdir "$COHORT/repeat-$repeat"
  for prefix in native cpu; do
    for suffix in '' _wrong_texture _wrong_sampler _wrong_buffer _no_dispatch; do
      python3 bridge/tools/public_icb_texture.py run --build "$BUILD" \
        --mode "$prefix$suffix" --out "$COHORT/repeat-$repeat/$prefix$suffix" \
        --reservation-root "$RESERVATION_ROOT" || break 3
    done
  done
done

python3 bridge/tools/audit_icb_texture.py "$COHORT" --out "$NEW_RECEIPT"
python3 -m unittest discover -s tests
python3 tools/check_publication.py
```

Every Metal host, including metadata-only, runs as an immutable signed copy
under the common reservation. A failed or timed-out host stops the cohort;
inspect that exact process/session before another attempt. Build and CPU
verification do not submit GPU work. The whole-source build checks current
runtime sources against its manifest before linking.

## Next integration work

The next target is GPU-generated commands selecting native texture argument
buffers, followed by explicit retained read-only indirect-resource/sampler
ownership in their resource catalogue. These are distinct from this CPU-encoded
ICB qualification. Preserve native texture/sampler encoding, exact command
invariants and existing resource functionality throughout that work.

A subsequent [GPU-generated texture-command qualification](GPU_ICB_TEXTURE_ARGUMENTS.md) now covers the bounded two-bank compute path. The figures above remain the original CPU-encoded ICB reception.
