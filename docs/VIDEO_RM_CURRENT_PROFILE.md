# Current RM profile observation without opening a client

The historical root-client allocation witness remains tied to an older
[system profile](VIDEO_PROFILE_DRIFT.md). A separate signed, nonprivileged
probe now observes the current file hashes, selected IOKit code in its own
process and the target NVDA service. It contains no `IOServiceOpen` or RM-call
path and does not change the old witness or its acceptance profile.

## Result

On October 28, two separate UID 501 processes each checked the running kernel
UUID, five on-disk hashes (including the current GeForce and NVDAResman files),
and three pinned IOKit code regions loaded in that process. They each found
four `NVDA` services matching the NVIDIA PCI property search, then selected
exactly one using the supplied registry ID and the immediate parent class/name
`IONDRVDevice` / `NVDA,Display-A`. The observed ID was `4294968425` in this
boot; registry IDs are ephemeral and must be rediscovered after a restart.

These four services are not four GPUs: the separately inspected IOService tree
shows four display children beneath the same GTX PCI device. A filter matching
only class and PCI identity is therefore ambiguous. The matching property
search includes ancestor/recursive traversal; it does not independently prove
the complete service topology or that the selected service accepts a client.
The exact target ID and parent check are required for this observation.

A wrong IOKit hash was refused before registry enumeration; a wrong registry
ID was refused after enumeration. Both positive observations and both
controls returned zero open attempts, RM calls and GPU dispatches in their
own output. The [audit](video-rm-current-profile-validation.json) rechecks
four signed, nonoverlapping hosts, terminal cooperative reservations, outputs,
source and binary hashes, and a second byte-identical build. The program
imports `IOConnectCallMethod` only to verify its own loaded code address; it
does not invoke that method. This does not establish a loaded kernel-code hash
or trace hidden activity by other processes.

An initial development control completed without opening anything but its
launcher failed to write a manifest because its reservation module was absent
from the launcher's directory. The job registry and reservation state showed
that process terminal before the proper frozen runner was used. A first probe
then correctly refused the four-way ambiguous match twice. These attempts are
retained in the local laboratory and are not counted as positive observations.

No old acceptance pin was replaced. Root allocation/free, a device object,
class-list retrieval and hardware video remain unexecuted and unqualified on
the current profile. Matching UUIDs or own-process IOKit bytes do not prove
that all loaded NVIDIA code matches the on-disk image.

## Reproduction

The source is [`profile_probe.mm`](../bridge/experiments/video_rm_profile/profile_probe.mm).
The historical receipt auditor accepts only the exact recorded source, two
builds and four capture directories; its pins deliberately reject different
host results. It needs the existing local lab, including the frozen shared
runner and reservation module. Proprietary components are not distributed.

```sh
R="$KP_LAB/bridge/results"
python3 -B bridge/experiments/video_rm_profile/audit.py \
  --source bridge/experiments/video_rm_profile/profile_probe.mm \
  --original-build "$R/video-rm-current-profile-build-20261028-02" \
  --rebuild "$R/video-rm-current-profile-build-20261028-03" \
  --runs "$R/video-rm-current-profile-v2-wrong-hash-01-20261028-01" \
         "$R/video-rm-current-profile-v2-wrong-id-01-20261028-01" \
         "$R/video-rm-current-profile-v2-valid-01-20261028-01" \
         "$R/video-rm-current-profile-v2-valid-02-20261028-01" \
  --out /absolute/new-profile-audit.json
```

The build used Apple clang 17.0.0 with `-arch x86_64 -O1 -std=c++17
-fobjc-arc -Wno-deprecated-declarations`, Foundation and IOKit. The frozen
`run_sdk_host.py` signs a new copy and uses the shared cooperative reservation.
A new cohort needs fresh paths, a freshly observed registry ID and an
independent review of any changed file/code pins; it must not silently update
the privileged witness.
