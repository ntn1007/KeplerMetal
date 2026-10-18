# Native NVIDIA port access under UID 0

The human executed the previously prepared bounded administrator experiment
on 2026-10-18. Independent inspection of its frozen sources, signatures and
raw process records confirms one normal `NVDA` user-client open followed by
one successful close. This resolves that test's administrator-access step;
it does not qualify a decoder or the RM packet ABI.

| Observation | Verified result |
| --- | --- |
| Selected service | `NVDA`, PCI `10de:1198`, registry ID `4294968459` |
| User-client type | Normal `0x80000000`; no exclusive type |
| Coordinator and wrapper | UID 501 |
| Leaf before and after the operation | Same PID/thread, UID 0 / EUID 0, inherited reservation |
| `IOServiceOpen` / `IOServiceClose` | One call each, both status `0` |
| Native termination | Normal exit, no kill, fresh process table shows the helper processes absent |
| External RM methods / host GPU commands / video images | `0` / `0` / `0` |

The earlier ordinary-user case returned `OPEN_REFUSED` at `-536870201` for the
same service ID and user-client type. The administrator result changes port
access, not the remaining packet layout, decoder setup or image verification.
Effects internal to the driver's open/close implementation were not traced.

The leaf's sources enforce UID 0 and the inherited common lab lease. The
unprivileged wrapper pins that leaf by hash, forwards the lease and invokes
only its fixed `open` operation after human authentication. No service, driver,
OCLP, protection, setuid executable or sudoers configuration was installed.
The agent did not request or execute an additional privileged action.

[The sanitized audit](video-admin-access-validation.json) pins the executed
local helper's source and binary identities and raw-record hashes. Full local
captures and generated host profiles are not distributed. This documents the
audited local experiment, not a new standalone administrator launcher in this
release. No new administrator run is needed for the resident-batch experiment.

The next video investigation must identify the exact original RM emitter's
request/response contract before sending any newly constructed method packet.
A successful open alone is not evidence of hardware decoding.
