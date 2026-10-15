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
| Function argument encoders | Real native metadata preserved; library `ee9c71cb…`: 64 dataflow trials, 60 three-pointer trials and 4 encoder-reuse trials PASS; 12 same-source M1 trials / 156 common files matched | Bounded layout/producer contract; not a general Metal implementation |
| Native resource ABI | Producers load root pointer and launch dimensions from native CB1; 64 trials PASS after correcting an initial experimental CB0 mapping failure | Producer qualification uses one 32-thread group; other producer geometries remain unqualified |
| Synchronous function pipeline creation | Library `b19f7809…`: six registered variants returned through the ordinary public function factory; 64 trials, 5,035,008 exact uint32 values, 1,258,752 counted consumer invocations, 81,473,504 guard bytes; 84 argument rejections; 4 metadata/lifetime trials / 38 checks; 12 same-source M1 trials / 156 common files matched | Explicit registration/pins required. Descriptor, reflection and asynchronous factory paths are not extended. Unregistered native compilation still reports `air.compute_pipeline_state`; native encoder setter limitation remains outside our adapter |
| Managed dirty-buffer abandonment | Native-only diagnostics reproduced retained objects in bounded cases | Earlier cancellation FAIL retained; no general permanent-leak claim or workaround |
| Video / display / power / full VRAM management | Inventory and focused investigations | No full modernization or complete hardware coverage demonstrated |
| Linux/FreeBSD driver comparison | Reference archives studied and differences classified | No proprietary correction has been ported into the installed macOS driver |

The final library also passed 9 targeted three-pointer regression cases. A separate complete rebuild of all seven runtime objects from the public source (`f110430d…`) passed 4 GTX smoke trials with 457,728 exact uint32 values, 114,432 counted consumer invocations and 5,052,992 guard bytes. Its full 64-case suite was NOT RUN; it does not inherit the other artifact's qualification.

## Evidence boundaries

Milestone library hashes:

- Last published device-argument qualification: `edd584b05b94ca536ab65a1976440a52e521a15657e0b02f843be1a422d7b176`.
- Function smoke candidate: `77cbf183798f9883e3ebf6c61f49c076a3ad20d39a451a5e312bfa323c31bf31`.
- Subsequent function candidate: `ee9c71cb26cb4d109be8875424e0f0be487c8f91a671f26ce0068348172ec5af`.
- Current registered synchronous pipeline candidate: `b19f78099eb6bb9b644e481902cbcbed829760f8e5ff61114d2bbb5fbaf66dd7`.

These are historical build identities, not downloadable artifacts. The original source tree had no Git commit. `SOURCE_SNAPSHOT.json` records the exported source hashes and publication edits. Private binary result archives are intentionally excluded; the published tools allow inspection of the checks, but a summary is not independent proof of hardware execution. A new full source build has a different artifact identity and does not inherit old GPU qualification.

Current work: extend descriptor/reflection/asynchronous pipeline contracts and function/library registration conservatively, then continue the remaining driver/hardware categories. The synchronous factory is now integrated for the explicitly registered subset; transparent support for arbitrary application libraries remains open. Preserve validated native behavior rather than reimplementing it unnecessarily.

No new driver performance benchmark is claimed. Earlier application batching improvements mixed submission and wait effects; NAK was slower than the native path on two tested workloads. API extension, correctness repair, and application optimization are distinct results.
