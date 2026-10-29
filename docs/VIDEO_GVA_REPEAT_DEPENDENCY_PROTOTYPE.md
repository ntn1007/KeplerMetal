# Repeatable dependency observer: CPU prototype

An experimental process-local variant of the dependency observer now uses the
same epoch gate as the [metadata prototype](VIDEO_GVA_REPEAT_METADATA_PROTOTYPE.md).
Each accepted scope resets its own events and counters, admits readers for its
epoch, disables recording and drains before snapshotting. Concurrent scope
creation is refused. Successive video-create records are named separately
(`dependency.json`, then `dependency-2.json`, and so on). If a drain times
out, the gate remains unavailable in that process. A failed write or release
is logged; after a forwarded session creation, the wrapper preserves the
original returned status rather than inventing an error and leaking a session.

Two CPU processes each exercised three independent observer scopes using real
`IORegistryEntrySearchCFProperty` calls on the public root entry. They checked
present and absent keys, original return values, one event per scope, drained
records, concurrent-begin refusal and refusal of a non-owner snapshot. Two
other CPU processes each ran three `KPVideoDependencyInspect` scopes with the
pinned local profile: twelve positive/negative public IOKit controls passed
across those scopes. These are bounded tests; they do not establish correctness
for all concurrent schedules or failures.

The test library includes a compile-time CPU-only seam; it is not a production
library. **No `VTDecompressionSessionCreate` was invoked by these tests.**
The repeatable metadata and dependency variants have not yet been linked
into the multi-session H.264 client. Their interaction, per-request video
records, and refusal/cleanup paths in that client remain unqualified. No GPU,
NVIDIA video engine, macOS system component or OCLP was modified or executed.
No hardware video or performance improvement is claimed.

[Qualification receipt](video-gva-repeat-dependency-prototype-validation.json)
contains source, build and log hashes without binaries. Next, link the two
variants into an isolated repeat client, qualify three CPU sessions and
negative controls, and only then examine the hardware-required path.

## Reproduction

Requires the privately retained pinned base profile and Xcode tools on the
matching Intel macOS system. The output must not already exist:

```bash
python3 bridge/experiments/video_gva_repeat_sessions/qualify_dependency.py \
  --base '/path/to/nvidia-880m-lab/bridge/results/gva-property-build-20261028-01' \
  --out '/path/to/new-lab-results/repeat-dependency-qualification'
```

The script builds and ad-hoc signs local binaries and uses the pinned profile
only for local CPU inspection; it does not install them or alter the original
profile. The supported runtime profile is deliberately narrow.
