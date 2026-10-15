# Status at the source export, 2026-10-15

The full goal remains **incomplete**. This is a development source snapshot with private ABI dependencies, not a production display-driver release. No percentage of total completion is assigned: the remaining hardware/API scope is not bounded enough to make that number meaningful.

| Area | Evidence from local work | Remaining limitation |
| --- | --- | --- |
| AIR → NIR → NAK SM30 | Compiled programs executed on the reference GTX with CPU output comparisons | Does not implement a Metal runtime or replace the installed compiler |
| Shared memory / atomics | Earlier bounded cohorts covered 48 KiB/group and 1,024 threads/group | Scope is the tested programs and synchronization patterns |
| Native weak-CAS result | Causal repair with original/replay/NOP controls; later semantic recognition | Targeted, process-local repair; not every Invalid Resource issue or all CAS programs are solved |
| Native heaps, aliases, fences, events | Working scenarios using existing native APIs | Existing capabilities, not functions newly added by KeplerMetal |
| CPU/generated command paths | Scoped native-command adaptation with CPU oracles, guards and negative controls | Custom IR ABI; Apple ICB identity and `gpuResourceID` remain unsupported |
| Device argument encoders | Fully selected milestone: 192 cases, 8,239,104 uint32 values, 2,059,776 invocations, 127,576,064 guard bytes; 12 M1 reference trials / 156 common semantic files matched | Counts include selected controls/lifetime cases, not full Metal conformance; no general speed claim |
| Three-pointer argument layout | 60 selected typed trials plus 3 legacy trials passed on the preceding library | Requires qualification on the later function-encoder candidate |
| Function argument encoders | Real native function metadata preserved; basic smoke: 4 trials, 457,728 uint32 / 114,432 invocations correct on candidate `77cbf183…`; latest candidate: 4 CPU-only metadata/ownership trials, 34 checks PASS | Latest candidate `ee9c71cb…` final GPU qualification NOT RUN |
| Native producer pipeline creation | Reproduced `Unsupported indirect argument kind "air.compute_pipeline_state"`; native encoder pipeline setter assertion also observed | Ordinary pipeline creation and transparent app integration remain open |
| Managed dirty-buffer abandonment | Native-only diagnostics reproduced retained objects in bounded cases | Earlier cancellation FAIL retained; no general permanent-leak claim or workaround |
| Video / display / power / full VRAM management | Inventory and focused investigations | No full modernization or complete hardware coverage demonstrated |
| Linux/FreeBSD driver comparison | Reference archives studied and differences classified | No proprietary correction has been ported into the installed macOS driver |

## Evidence boundaries

Milestone library hashes:

- Last published device-argument qualification: `edd584b05b94ca536ab65a1976440a52e521a15657e0b02f843be1a422d7b176`.
- Function smoke candidate: `77cbf183798f9883e3ebf6c61f49c076a3ad20d39a451a5e312bfa323c31bf31`.
- Subsequent function candidate: `ee9c71cb26cb4d109be8875424e0f0be487c8f91a671f26ce0068348172ec5af`.

These are historical build identities, not downloadable artifacts. The original source tree had no Git commit. `SOURCE_SNAPSHOT.json` records the exported source hashes and publication edits. Private binary result archives are intentionally excluded; the published tools allow inspection of the checks, but a summary is not independent proof of hardware execution. A new full source build has a different artifact identity and does not inherit old GPU qualification.

Current work: qualify the final function-encoder candidate, extend ordinary pipeline creation conservatively, then examine the remaining driver/hardware categories. Preserve validated native behavior rather than reimplementing it unnecessarily.

No new driver performance benchmark is claimed. Earlier application batching improvements mixed submission and wait effects; NAK was slower than the native path on two tested workloads. API extension, correctness repair, and application optimization are distinct results.
