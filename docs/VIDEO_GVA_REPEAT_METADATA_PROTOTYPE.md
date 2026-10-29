# Repeatable metadata observer: CPU prototype

A process-local experimental variant of the metadata observer now supports
sequential observation scopes. It leaves the original observer untouched.
A scope has one owner; another thread cannot begin or snapshot that scope.
Reader admission uses an epoch and an in-flight counter: a reader delayed
from an earlier epoch is rejected after a later scope begins. Closing a scope
stops admissions and waits for admitted readers before copying results. A
drain timeout poisons the gate and prevents a new scope in that process.

Two independent CPU processes exercised **three metadata generations each**
using real Core Foundation retain calls. Each generation captured its own
synthetic control exactly once and returned a complete, drained snapshot;
invalid sites, a second begin and a non-owner snapshot were refused. Two
separate gate-test processes exercised **600 total cycles**, each with four
concurrent worker threads, plus stale tickets, drain and sticky timeout cases.
These bounded tests are evidence for the exercised cases, not a proof against
all schedules or failures.

This is an observer prototype, not a driver or API feature. It has **not**
been connected to the H.264 repeat host or qualified on AppleGVA callsites.
The separate dependency observer still has its own single-use guard. No GPU,
video decoder, NVIDIA code, macOS system component or OCLP was modified or
executed in these CPU tests. No hardware-video or performance claim follows.

The [sanitized qualification](video-gva-repeat-metadata-prototype-validation.json)
records source, binary and log hashes; binaries remain local. The next step is
to design and test the dependency observer's repeatable scope and then bind
both variants to the multi-session host, with per-request records and negative
controls, before considering a hardware-required run.

## Reproduction

On an Intel macOS machine with Xcode tools and the retained project source:

```bash
python3 bridge/experiments/video_gva_repeat_sessions/qualify_metadata.py \
  --out '/path/to/new-lab-results/repeat-metadata-qualification'
```

The destination must not exist. The script copies original sources to that
folder, compiles x86-64 CPU-only programs, signs the generated local binaries
ad hoc, verifies their signatures and records two runs of each test.
