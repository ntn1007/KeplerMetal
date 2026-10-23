# Local-memory accounting groundwork, 2026-10-23

The existing large-scratch client now records a bounded memory ledger alongside
its integer CPU oracle and no-dispatch controls. This is diagnostic tooling;
it changes neither the import runtime nor the installed driver. The new client
builds on Intel macOS, but its GPU qualification is **BLOCKED** by a changed
installed driver profile. No new GPU result or speedup is claimed.

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

## Current profile refusal

macOS still reports 26.7.1 / 25G241, with SDK 26.2. Against the 87-file reference
used for the 19 October qualification, seven files differ: GeForce, the Metal
driver, the Metal framework entry and `MetalOld.dylib`, two OCLP application
files, and the root-patch record. The latter records patching on 20 October.

| Installed driver | SHA-256 |
| --- | --- |
| Qualified `GeForceMTLDriver` profile | `2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054` |
| Observed on 23 October | `e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645` |

The Python launcher now checks this profile before reserving/signing/starting
a Metal process. The actual changed-profile attempt was refused without
creating a run directory or launching the client. The original host-side check
remains. Hashes and private ABI checks were not relaxed. A version string alone
does not establish binary compatibility.

The updated application and constructor client both compiled and linked against
the unchanged seven-object archive
`364bf6599f0ff10cc389449189a3c6a5ca96dba138d99f90144a07878d88e585`.
The regenerated carrier still matched its qualified hash. Two archived baseline
cases were reverified on the CPU: 1,408 exact output words and 1,408 expected
words absent in the negative control. These are historical captures, not fresh
GPU executions. The previous archive qualification remains historical evidence
for its original system profile.

## Reproduction and next action

Run the portable tests first:

```sh
python3 -B -m unittest discover -s tests -v
python3 tools/check_publication.py
```

Use the source-only generation/build commands in
[LARGE_LOCAL_MEMORY.md](LARGE_LOCAL_MEMORY.md), with `--extended`. Locally
generated programs and the already qualified runtime archive may be reused
only after their hashes have been checked. To request the new cohort:

```sh
python3 -B bridge/tools/qualify_public_large_scratch.py \
  --build "$KP_WORK/hosts-extended" --out "$KP_WORK/accounting" \
  --reservation-root "$KP_LAB" --suite accounting
```

This requests native/imported 8/16 KiB cases, a native/imported pressure pair,
forced spill, the local control and three no-dispatch controls. On the current
iMac it is expected to stop at the profile check. The next work is to inspect
and separately qualify the changed driver/runtime profile before executing this
cohort under the shared reservation. Do not substitute the new file hash into
old private-ABI profiles merely to run the test. No system rollback is required
or performed by these tools.
