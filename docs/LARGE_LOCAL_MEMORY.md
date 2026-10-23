# Qualified 8/16 KiB private local-memory imports

The original 19 October results below retain their original system profile.
The separately investigated 23 October signature variant and current-boot GPU
identity are described in [DRIVER_PROFILES.md](DRIVER_PROFILES.md); fresh
accounting/CAS qualification is tracked in [MEMORY_ACCOUNTING.md](MEMORY_ACCOUNTING.md).

The opt-in `KPCreateLocalMemoryPipeline` path now accepts two additional native
carrier profiles: `local2048` (8,192 bytes per thread) and `local4096` (16,384
bytes per thread). This is private local/scratch memory, separate from shared
threadgroup memory. The native NVIDIA compiler already supports these private
arrays; this change extends the bounded imported-program path.

The runtime change is limited to the two names/frame sizes and a separate
carrier-library fingerprint for frames larger than 4 KiB. Existing names keep
their original fingerprint. The allocator formula, private ABI checks, code and
register limits, ownership, import serialization and constructor restoration are
unchanged. The shared MRC implementation remains `KeplerNativeCAS.mm`; its CAS
correction is preserved rather than newly generalized by this change.

## Artifact-specific qualification

On 2026-10-19, all seven core objects were rebuilt from public text using
`tools/build_from_source.py`, SDK 26.2 and Apple clang 17, targeting baseline
x86_64. The resulting archive has SHA-256
`364bf6599f0ff10cc389449189a3c6a5ca96dba138d99f90144a07878d88e585`.
It passed the whole-archive link and CPU link check, then the following separate
qualification on the GTX 880M under macOS 26.7.1 / 25G241:

| Cohort | Compute dispatches | Exact output uint32 values | Guard bytes | Expected computation words absent without dispatch |
| --- | ---: | ---: | ---: | ---: |
| New profiles, baseline | 6 | 2,816 | 6,144 | 2,816 |
| New profiles, extended launch matrix | 24 | 35,872 | 24,576 | 35,872 |
| Legacy local/control/spill profiles | 96 | 143,488 | 61,440 | 35,872 |
| Differential instruction witness | 6 | 2,816 | 6,144 | 2,816 |
| CAS, descriptor/allocation imports and local postludes | 94 | 427,128 | 13,568 | 0 |
| **Total** | **226** | **612,120** | **111,872** | **77,376** |

The total is 286 completed command buffers: 226 compute dispatches and 60
no-kernel/blit controls. The CAS cohort includes 106,650 correct CAS operations,
90 CAS dispatches and four subsequent compute postludes. Constructor-only
qualification covers two valid creations and 28 mixed cases (26 expected
refusals, two valid recoveries), plus eight separate CAS refusal cases. These
constructor/refusal cases submit no command buffers. Twenty-six signed hosts
completed under the same cooperative reservation, without overlapping cohorts.

The extended matrix uses group sizes 1, 31, 32, 33, 64, 128, 256, 512 and 1,024,
including selected multigroup launches. Every launch uses complete, in-bounds
threadgroups. It does not qualify nonuniform threadgroups. Both new SM30
programs use 24 GPRs, 3,456 bytes of code and no external call-stack reserve.
Full inputs and guarded outputs are checked against the independent integer CPU
oracle; the checksum exercises the private array, rather than reading back
every scratch location.

For the execution witness, only instruction word 407 (byte offset 3,256) changes
between each normal and tagged program. The native-style fourth output word
uses `0xcafe0000 ^ gid`; the tagged program uses `0x4e414b00 ^ gid`. Across the
paired new-profile runs, all 704 varying witnesses change as specified, while
the other 2,112 arithmetic output words, inputs and guards match. The host and
carrier bytes are identical in each pair, and caller-owned import buffers are
wiped before commit. Together with the no-dispatch controls, this supports
execution of the imported computation rather than detection or allocation alone.
It is not a hardware-resident instruction-memory readback.

This archive has its own qualification. The earlier isolated six-object
candidate (`e9832d3fd12dcfa06208ede1eb9b1106bb783ca9f1ccfe24da91f33e3e54ae43`)
and historical native/M1 references remain separate frozen evidence. The current
cohort did not rerun every previously published Metal/graphics/video experiment.
Machine-readable counts and pins are in
[large-local-memory-validation.json](large-local-memory-validation.json).

All 62 portable CPU tests pass, including five new checks that reject an
incomplete archive, changed objects, changed runtime text or a changed archive.
These portable tests perform no GPU execution.

## Reproduction from published text

Obtain the open source dependencies using [DEPENDENCIES.md](DEPENDENCIES.md).
The recorded reference is Mesa 26.2.4 / upstream reference
`96cb43121031992b85767f9c1be8f3f48e22b1d2`, with this project's SM30 patches.
The effective local Mesa tree was extracted without a nested Git checkout;
the generator fingerprints every linked archive instead of treating the
upstream reference as proof of its effective bytes. Full Xcode with Metal tools,
SDK 26.2 and x86_64 are required by this narrowly qualified workflow.

Run from the repository root. Set `KP_MESA` to the existing patched Mesa build,
`KP_LAB` to the **one existing reservation root** for this physical GTX, and
`KP_WORK` to an output parent with space available. Each output below must be
new. Do not run these GPU commands concurrently with another cohort.

```sh
: "${KP_MESA:?Set the patched Mesa build directory}"
: "${KP_LAB:?Set the existing common bridge reservation root}"
: "${KP_WORK:?Set an output parent, preferably on the data disk}"
mkdir -p "$KP_WORK"
python3 -B tools/build_from_source.py --out build/local-8-16
KP_LIBRARY="$PWD/build/local-8-16"

python3 -B bridge/tools/public_large_scratch.py programs --mesa-build "$KP_MESA" --out "$KP_WORK/programs"
python3 -B bridge/tools/public_large_scratch.py programs --mesa-build "$KP_MESA" --out "$KP_WORK/witness-programs" --witness

python3 -B bridge/tools/public_large_scratch.py build --library "$KP_LIBRARY" --programs "$KP_WORK/programs" --out "$KP_WORK/hosts-baseline"
python3 -B bridge/tools/public_large_scratch.py build --library "$KP_LIBRARY" --programs "$KP_WORK/programs" --out "$KP_WORK/hosts-extended" --extended
python3 -B bridge/tools/public_large_scratch.py build --library "$KP_LIBRARY" --programs "$KP_WORK/programs" --out "$KP_WORK/hosts-legacy" --extended --carrier legacy
python3 -B bridge/tools/public_large_scratch.py build --library "$KP_LIBRARY" --programs "$KP_WORK/witness-programs" --out "$KP_WORK/hosts-witness"

python3 -B bridge/tools/public_large_scratch.py run --build "$KP_WORK/hosts-baseline" --out "$KP_WORK/construct" --reservation-root "$KP_LAB" --contracts --mode construct
python3 -B bridge/tools/public_large_scratch.py run --build "$KP_WORK/hosts-baseline" --out "$KP_WORK/refusals" --reservation-root "$KP_LAB" --contracts --mode negative
python3 -B bridge/tools/qualify_public_large_scratch.py --build "$KP_WORK/hosts-baseline" --out "$KP_WORK/baseline" --reservation-root "$KP_LAB" --suite baseline
python3 -B bridge/tools/qualify_public_large_scratch.py --build "$KP_WORK/hosts-extended" --out "$KP_WORK/extended" --reservation-root "$KP_LAB" --suite extended
python3 -B bridge/tools/qualify_public_large_scratch.py --build "$KP_WORK/hosts-legacy" --out "$KP_WORK/legacy" --reservation-root "$KP_LAB" --suite legacy
python3 -B bridge/tools/qualify_public_large_scratch.py --build "$KP_WORK/hosts-witness" --out "$KP_WORK/witness" --reservation-root "$KP_LAB" --suite witness
```

The builds submit no GPU work. The runner verifies frozen sources, programs,
library provenance and executable hashes, then creates an immutable signed
process through the common reservation. The suite stops on the first failure
and records its exact command without retrying. Keep all failed results; check
the actual process and lease before any further submission. Do not use Python
optimization flags, which would disable assertion-based contract checks.

The two MSL sources are included. Rebuilt carriers must match
`62a49cf2ea3a3e4daec94cb7cf6c35abb2828101b74c47a8ea6d16d042137424`
for the large profiles and
`bb052086f1a0f8ce1a2cad8da00c74926ac47abe0d0b95d3b1f66cf24f4d3d5d`
for legacy profiles. A mismatch requires separate qualification, not changing a
hash merely to get past the check. Manifests retain the actual hashes of the
archive built on your machine; the measured archive hash above is not a claim
that every toolchain/path produces an identical static archive.

The CAS coexistence client additionally needs the earlier **locally generated**
CAS/native-allocation asset bundle described in
[NATIVE_ALLOCATION_API.md](NATIVE_ALLOCATION_API.md). Set `KP_CAS_ASSETS` to that
build directory with `inputs.json` and `assets/`; its compiled assets are not
distributed. The following rebuilds the published coexistence client against
the same new seven-object archive and supplements its large-profile assets:

```sh
: "${KP_CAS_ASSETS:?Set the existing locally generated coexistence build}"
python3 -B bridge/tools/public_large_scratch_cas.py build --library "$KP_LIBRARY" --asset-build "$KP_CAS_ASSETS" --large-build "$KP_WORK/hosts-baseline" --out "$KP_WORK/cas-build"
python3 -B bridge/tools/public_large_scratch_cas.py run --build "$KP_WORK/cas-build" --out "$KP_WORK/cas-refusals" --reservation-root "$KP_LAB" --mode negative
python3 -B bridge/tools/public_large_scratch_cas.py run --build "$KP_WORK/cas-build" --out "$KP_WORK/cas-execute" --reservation-root "$KP_LAB" --mode execute
```

This preserves the existing prerequisite boundary; it is not an automatic
clean-checkout bootstrap of all older CAS/allocation fixtures. Numeric oracles
and refusal tests are published. Raw results, native compiler containers,
generated GPU programs, SDKs and vendor binaries stay local.

## Limits and next work

This is explicit level-1 laboratory integration through the opt-in API. It
extends an imported-program profile; it does not install a modernized NVIDIA
driver or make these functions transparently available to unmodified apps.
The 83 tracked system files and four additional system pins, including OCLP,
were checked unchanged. No privileged RM method was called.

Physical VRAM consumption, scratch placement/occupancy, maximum sustainable
scratch pressure, and performance remain unmeasured. No performance gain or
general Metal 3/4 support is claimed. The next useful work is wider scratch and
memory-pressure qualification, followed by a separately measured workload;
native video and installed-driver modernization remain independent work.
