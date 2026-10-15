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
| Registered pipeline factory contracts | Library `c8571cf1…`: six public factory variants, 128 GTX trials, 12,358,656 exact uint32 results, 3,089,664 counted consumer invocations and 165,449,536 guard bytes; 17 supported CPU variants, 24 expected rejections, one pending asynchronous scope-release case; 12 same-source M1 trials / 156 common files matched | Six functions need explicit registration/pins. Reflection is an adapter backed by native argument metadata. Descriptor max threads uses automatic/default 0; the native constructor returned 1,024 for a request of 32, so smaller limits are refused. No arbitrary-library compilation or transparent application integration |
| CAS transport regression | After a same-thread descriptor import, 106,650 CAS operations / 90 submissions passed; eight import/pin rejections remained effective | Bounded native CAS repairs and transport-state cleanup, not a general installed compiler repair |
| Managed dirty-buffer abandonment | Native-only diagnostics reproduced retained objects in bounded cases | Earlier cancellation FAIL retained; no general permanent-leak claim or workaround |
| Video / display / power / full VRAM management | Inventory and focused investigations | No full modernization or complete hardware coverage demonstrated |
| Linux/FreeBSD driver comparison | Reference archives studied and differences classified | No proprietary correction has been ported into the installed macOS driver |

The final library also passed 9 targeted three-pointer regression cases. A separate complete rebuild of all seven runtime objects from the public source (`f110430d…`) passed 4 GTX smoke trials with 457,728 exact uint32 values, 114,432 counted consumer invocations and 5,052,992 guard bytes. Its full 64-case suite was NOT RUN; it does not inherit the other artifact's qualification.

## Evidence boundaries

Milestone library hashes:

- Last published device-argument qualification: `edd584b05b94ca536ab65a1976440a52e521a15657e0b02f843be1a422d7b176`.
- Function smoke candidate: `77cbf183798f9883e3ebf6c61f49c076a3ad20d39a451a5e312bfa323c31bf31`.
- Subsequent function candidate: `ee9c71cb26cb4d109be8875424e0f0be487c8f91a671f26ce0068348172ec5af`.
- Previous registered synchronous pipeline candidate: `b19f78099eb6bb9b644e481902cbcbed829760f8e5ff61114d2bbb5fbaf66dd7`.

- Current six-factory candidate: `c8571cf130546db4bc224573b0bb684c3cd537df95df7262be266b36a200869e`.

These are historical build identities, not downloadable artifacts. The original source tree had no Git commit. `SOURCE_SNAPSHOT.json` records the exported source hashes and publication edits. Private binary result archives are intentionally excluded; the published tools allow inspection of the checks, but a summary is not independent proof of hardware execution. A new full source build has a different artifact identity and does not inherit old GPU qualification.

Current work: qualify additional descriptor properties, address the smaller-thread-limit behavior, and extend function/library integration conservatively, then continue the remaining driver/hardware categories. The six factories are integrated for the explicitly registered subset; transparent support for arbitrary application libraries remains open. Preserve validated native behavior rather than reimplementing it unnecessarily. [Detailed contract](NATIVE_FUNCTION_PIPELINES.md) and [current validation summary](pipeline-contract-validation.json).

No new driver performance benchmark is claimed. Earlier application batching improvements mixed submission and wait effects; NAK was slower than the native path on two tested workloads. API extension, correctness repair, and application optimization are distinct results.

The current public-source seven-object rebuild (`0351b1bd26971e3f7c9e8b77d89a9babd8a9c1fb19cec3cadc38b30bf26f7f2c`) passed the full archive link and CPU link check, then four asynchronous-descriptor GTX smoke trials: 457,728 exact uint32 values, 114,432 counted consumer invocations and 5,052,992 guard bytes. The 128-trial suite was NOT RUN on this separately rebuilt artifact.
