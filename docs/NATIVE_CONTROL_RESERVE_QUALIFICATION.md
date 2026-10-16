# Native allocation correction: qualification and remaining integration

The allocation-only experiment now passes **228 GPU trials on 17 distinct native program profiles**. The unchanged NVIDIA programs produce 340,784 exact uint32 values and 85,196 per-invocation witnesses. This includes 24 additional lifetime trials on two of those profiles. The shared runtime and installed driver are unchanged: the correction still requires the explicit test application.

[Machine-readable evidence](native-control-reserve-qualification.json) · [Initial two-profile finding and reproduction](NATIVE_CONTROL_RESERVE.md).

## Scope of the new evidence

| Cohort | Trials/cases | Actual result |
| --- | ---: | --- |
| 17 native program profiles | 204 GPU trials | Exact CPU-oracle results |
| Input overwrite and pool-drain probes | 24 GPU trials | Exact results after construction inputs are overwritten and the factory pool ends |
| Original/replay and rounded reservation at65/96 | 48 GPU trials | Original numerical failure remains; outputs stay A5 |
| Missing compute dispatch at65/96 | 24 trials | A5 output remains, as required |
| Invalid allocation contracts | 10 API cases | Rejected before dispatch; constructor restored and a native recovery PSO created |

All 35 cohorts terminated normally. There are 300 command buffers in the numerical/control cohorts, including 24 with copies but no compute dispatch. The API rejection cohort creates no command buffers. Command-buffer completion is checked separately from numerical correctness. Across these cohorts, 153,600 guard bytes and the full input buffers are checked.

The 17 native profiles comprise source depths0,64,65,66,67,68,69,70,71,72,80,88,96; a96 program that reloads bounds; a96 program with an entry witness; the768-value register-pressure case; and the sequential-loop96 case. The latter two have different numerical semantics and their own CPU oracles. This is a bounded sample, not arbitrary-shader qualification.

The corrected allocation preserves already-working native programs as well as repairing previously failing profiles. In particular, the sequential program has104,000 code bytes and the pressure program has a4,656-byte native spill frame. A blanket64KiB native-code ceiling or that frame size alone is therefore not the established explanation of the original nested-loop failure. The separate64KiB *import* policy remains unchanged.

## Stronger identity and ownership checks

The v5 implementation snapshots the actual incoming compiler payload before parsing it. It changes only metadata words9/11, retains the copied payload with the PSO, then checks both the code hash and the complete passed payload again after the original native constructor returns. The decoded allocation, instruction count, registers and native spill fields must match the pinned contract before a PSO is returned.

Candidate source SHA-256: `ecff9c4f83d25283cf35a31ac77f53bcc9d1032a77b21209aba07ce3c5795991`.

This proves identity of the constructor payload and correct GPU results under the tested native transport. It is not an independent readback of resident GPU instructions. Metadata words2/4 remain unknown variable fields whose actual incoming bytes are preserved. The4,096 reservation is still a tested value, not a universal or minimum formula.

The lifetime client supplies mutable certificate/hash inputs, overwrites them after PSO creation, exits the inner factory autorelease pool, and only then dispatches GPU work. The deep-control96 and register-pressure96 cases pass12 trials each. This exercises retained storage after that pool boundary; general concurrent creation, exceptions and arbitrary resource lifetimes still need their own qualification.

## Refusals and recovery

Six cases exercise the real native constructor with a wrong code hash, wrong GPR/control/frame certificate, downward reservation, or mismatching function. The invalid certificate is refused; the original valid native payload is passed unchanged to the native constructor and the candidate PSO is discarded. No corrupted shader or compiler container is submitted to the GPU.

Four earlier refusals cover an unaligned reservation, an oversized reservation, a short certificate and a nil device. After each refusal, the test verifies restoration of the constructor and creates an ordinary native depth0 PSO outside interception. These recovery checks create no queue or command buffer; they do not qualify a subsequent recovery kernel execution.

The48 failing replay/rounding trials are retained scientific comparison controls. Unexpected infrastructure failures or an unexpectedly successful defective control are not mapped automatically to success. The historical unmodified-native standard matrix remains failed at96.

## Independent comparisons and provenance

The final read-only verifier repeats the numerical arithmetic, full input/output and guard checks, reparses the original native captures, verifies frozen source/executable/runner hashes and checks each actual rejection reason. Eleven pair comparisons produce264 matching input/output file checks. These include original native controls, the archived exact-metallib M1 reference, equivalent changed-source96 programs and the lifetime probes.

The M1 reference is reused from the earlier milestone; no new M1 execution occurs here. Its documented group-size adaptations still apply. It supplies a semantic comparison, not SM30 execution or a speed comparison. The83 tracked system files and OCLP remain unchanged. Shared archive SHA-256 remains `63840c89786b0ad9c862d119335efb80e44cbc9cf54d8a00deca7c12c41ec1de`.

The public source includes the native constructor experiment, real refusal client, lifetime client, serial matrix runner and independent suite verifier. Historical result trees, vendor code, generated machine code and private host configuration are excluded. The verifier's fixed historical fixture layout is not present in a clean source checkout; new native observations can be regenerated using the [documented workflow](NATIVE_CONTROL_RESERVE.md).

Build a separate refusal host by adding `--contracts` to `build_native_reserve_experiment.py`, or a lifetime host with `--lifetime`. These options are mutually exclusive. The matrix runner accepts explicit frozen builds and fresh result directories through `--matrix FILE --out NEW_DIRECTORY`; all runs must share the designated laboratory reservation root. It does not retry a failed or unresolved session automatically.

## Next integration step

Factor this qualified behavior into the existing MRC native transport, sharing its import mutex and using a context scoped to the caller thread. Snapshot library/profile inputs for an explicit certified API, preserve the existing CAS/local-memory/descriptor paths, and test restoration, coexistence and concurrency on the resulting archive. The present standalone experiment must not be linked beside another independent constructor hook and presented as a common runtime integration.

No new Metal API, installed compiler/driver replacement, transparent unmodified-application integration or performance gain is claimed. Whole-device VRAM usage and throughput were not measured in this cohort. Full GTX hardware coverage remains incomplete.
