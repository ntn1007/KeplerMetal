# Local-memory accounting, 2026-10-23

The existing large-scratch client now records a bounded memory ledger alongside
its integer CPU oracle and no-dispatch controls. This is diagnostic tooling.
The earlier driver-profile refusal was investigated: only the CMS signature
payload of the Metal driver differs, and the original boot-specific GPU entry
ID also changed. An exact additional profile and a public PCI identity check
have now passed a separate bounded qualification. [Comparison, identity and limits](DRIVER_PROFILES.md).
The installed driver remains unchanged; no speedup is claimed.

## What the ledger means

Each trial records the exact lengths requested for the two Private buffers and
three Shared buffers, including guards and the 16-byte parameter block. Source
array bytes per invocation are separate from the imported carrier frame and
the NAK program's required scratch bytes. Native compiler frame sizes are left
unknown; in particular, a native `pressure96` shader is not assumed to use the
imported carrier's 224-byte frame.

Logical array/carrier demand is the declared per-invocation size multiplied by
the number of dispatched invocations. It is zero in no-dispatch controls. This
is not a simultaneous occupancy, allocation or physical residency measurement.
The finite pre-allocation limits are 8 MiB for each storage class's requested
buffer lengths and 64 MiB for each logical local-memory total. They are test
bounds, not hardware limits; no launch sizes or GPU programs have been expanded.

`MTLDevice.currentAllocatedSize` is sampled before trial buffers, after buffer
creation, after command completion, and after trial objects leave scope. The
trial-series endpoints are also recorded. These are API accounting samples;
deferred driver destruction and allocation caching may affect them. Deltas may
be negative. An unavailable selector is recorded as JSON `null`, never as zero.
Physical VRAM, scratch occupancy, maximum pressure and performance remain
unmeasured.

The independent verifier recomputes the ledger from trial dimensions and program
metadata. New builds require every ledger field and phase; they also pin the
verifier hash. Historical records without a ledger keep their old verification
shape. CPU fixtures test malformed requests, missing samples, unsupported
counters, native/import differences, no-dispatch semantics and misleading
measurement claims. Those fixtures are not GPU observations.

## Preserved initial profile refusal

macOS still reports 26.7.1 / 25G241, with SDK 26.2. Against the 87-file reference
used for the 19 October qualification, seven files differ: GeForce, the Metal
driver, the Metal framework entry and `MetalOld.dylib`, two OCLP application
files, and the root-patch record. The latter records patching on 20 October.

| Installed driver | SHA-256 |
| --- | --- |
| Qualified `GeForceMTLDriver` profile | `2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054` |
| Observed on 23 October | `e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645` |

The Python launcher checks the profile before reserving/signing/starting
a Metal process. The actual changed-profile attempt was refused without
creating a run directory or launching the client. The original host-side check
remains. Private ABI checks were not relaxed. A version string alone
does not establish binary compatibility.

The updated application and constructor client both compiled and linked against
the unchanged seven-object archive
`364bf6599f0ff10cc389449189a3c6a5ca96dba138d99f90144a07878d88e585`.
The regenerated carrier still matched its qualified hash. Two archived baseline
cases were reverified on the CPU: 1,408 exact output words and 1,408 expected
words absent in the negative control. These are historical captures, not fresh
GPU executions. The previous archive qualification remains historical evidence
for its original system profile.

## Fresh qualification on the current system

A new seven-object build from public text has SHA-256
`8a7ae8d7f9d3f38cbfdcdca9905a0aa648488ae9010b1ae731e995010e612e51`.
This final artifact has its own GTX qualification, separate from the original
archive and the intermediate accounting build:

| Cohort | Compute dispatches | Exact uint32 results | Guard bytes | Expected words absent without dispatch |
| --- | ---: | ---: | ---: | ---: |
| Native/imported arrays, controls and spills | 96 | 143,488 | 67,584 | 53,808 |
| CAS and four resource/import postludes | 94 | 427,128 | 13,568 | 0 |
| **Total** | **190** | **570,616** | **81,152** | **53,808** |

There are 226 completed command buffers including 36 no-kernel controls,
15 terminal/nonoverlapping signed hosts, 106,650 correct CAS operations,
30 constructor cases (26 expected refusals and four valid creations), and
eight separate CAS refusal cases. The final accounting cohort includes the
1–1,024-thread group-size matrix and selected multigroup launches. Seventy-two
paired native/imported input/output files match exactly. Caller-owned import
buffers are wiped before dispatch. These are computation/result observations,
not a readback of resident GPU instructions or a general compiler repair.

All 528 per-trial allocation-counter samples are available. The largest requested
Private/Shared buffer totals are 1,090,048 and 1,090,064 bytes respectively.
The largest declared per-trial local-array demand is 32 MiB. Completion-counter
deltas range from zero to 74,809,344 bytes; these API values are not physical
VRAM measurements, and are not interchangeable with the logical demand.

Ninety portable CPU tests pass. The independent audit rechecks file hashes,
CAS raw results, native-allocation proofs, postludes and nonoverlapping process
intervals. All 87 system reference files match the observations at the start of
this work. The changed files relative to 19 October were not rolled back.
The interrupted first build, diagnostic-runner metadata error, mixed-carrier
refusal, and obsolete CAS boot-ID gate remain preserved separately. Preliminary
and failed cohorts do not contribute to the final table. [Machine-readable
summary](driver-profile-validation.json).

Full graphics/ICB/FP64, video and power/display qualification on this profile
remains unfinished. There is no new performance benchmark, maximum-pressure
qualification, physical VRAM measurement or general Metal 3/4 claim.

## Reproduction

Run the portable tests first:

```sh
python3 -B -m unittest discover -s tests -v
python3 tools/check_publication.py
```

Use the source-only generation/build commands in
[LARGE_LOCAL_MEMORY.md](LARGE_LOCAL_MEMORY.md), with `--extended` for **both** the
large and legacy carrier hosts. Locally
generated programs and the already qualified runtime archive may be reused
only after their hashes have been checked. To request the new cohort:

```sh
python3 -B bridge/tools/qualify_public_large_scratch.py \
  --build "$KP_WORK/hosts-extended" --out "$KP_WORK/accounting" \
  --legacy-build "$KP_WORK/hosts-legacy" \
  --reservation-root "$KP_LAB" --suite accounting
```

This requests native/imported 8/16 KiB cases, a native/imported pressure pair,
forced spill, the local control and three no-dispatch controls. The two builds
must use the same seven-object runtime archive, client source and verifier.
Spill/control cases use the separately pinned legacy carrier; 8/16 KiB cases
use the separately pinned large carrier. The first mixed-carrier attempt was
correctly refused before dispatch and is preserved separately.

The installed file is never replaced, and no new hash is admitted automatically.
Unknown profiles still stop before host execution. New signature variants or
framework changes require investigation and separate qualification. No system
rollback is required or performed by these tools.
