# VideoToolbox reference client on Apple Silicon

Two reference cohorts ran the same six-frame H.264 fixture on an arm64 MacBook
with macOS 27.2. Each used four fresh processes: VideoToolbox software and
hardware-required sessions, each with and without a process-local observer.
All **48 output frames, 5,529,600 active NV12 bytes**, matched the pinned
FFmpeg software reference. In the four hardware-required sessions,
VideoToolbox's `UsingHardwareAcceleratedVideoDecoder` property returned success
and true. The software sessions explicitly disabled hardware, while that
property returned `-12900` and no value; that result is not interpreted as
false. This qualifies the tested reference clip, not general H.264 behavior.

The observer interposes the public `IOServiceOpen` and three `IOConnectCall*`
imports **in the test process** and forwards the calls unchanged. It calibrates
its host import using a null connection; no request is sent to a GPU by that
calibration. After successful opens it queries the service class and registry
name, then associates observed calls with the most recent matching returned
Mach port name. This is a process-local observation with read-only registry
queries, not a trace of every framework or service process. Port-name reuse and
other threads can limit association. Counters and event snapshots are not an
atomic snapshot of all framework execution.

In each observed software process, the successful recorded open identified
`IOSurfaceRoot` and no AGX service was recorded. In each observed
hardware-required process, successful recorded opens identified IOSurfaceRoot
and `AGXAcceleratorG13X`; the latter returned connection type `0x100005`.
Five observed `IOConnectCallStructMethod` calls associated with that most
recent AGX port had selector values 2, 0, 5, 258 and 256, and one observed
`IOConnectCallMethod` had selector 9. These are call observations across the
session and output-copy window: **their individual semantics and their role in
decoding are not established**. The equivalent plain processes prove the
fixture result does not require the observer, not that instrumentation has no
other effects.

The observer covers only its declared imports and process lifetime; it does not
trace pre-main bindings, direct traps, all imports, separate decoder services,
or GPU firmware. An unobserved selector does not prove it was never called.
AGX selectors and connection types cannot qualify the distinct NVIDIA/macOS
video ABI. No NVIDIA video request was sent or decoded here, and no performance
claim follows. This reference comparison does not justify forwarding the
previously refused NVIDIA request.

## Evidence and reproduction

[Independent two-cohort audit](video-m1-client-observer-validation.json)
checks the reference bytes, raw outputs, observer calibration, signed host
and library hashes and signatures, process-local call records and cooperative
reservation receipts. Source and fixture hashes were checked before and after
transfer. The signed test programs, original frames, raw logs and reservation
records remain private local artifacts; no Apple or NVIDIA driver is included.
The cooperative iMac laboratory reservation covers participating lab runners,
not unrelated MacBook workloads. No system, driver, firmware or OCLP change was
made.

Use the pinned fixture and reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md),
an authenticated SSH alias to the reference Mac, unique remote directories,
and fresh local output directories:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/video_m1_client_observer
python3 "$E/run.py" --lab "$LAB" --fixture /path/to/fixture \
  --reference /path/to/decoded.nv12 --host SSH_ALIAS \
  --remote-dir /absolute/new/remote-1 --out "$LAB/results/m1-vt-1"
python3 "$E/run.py" --lab "$LAB" --fixture /path/to/fixture \
  --reference /path/to/decoded.nv12 --host SSH_ALIAS \
  --remote-dir /absolute/new/remote-2 --out "$LAB/results/m1-vt-2"
scp SSH_ALIAS:/absolute/new/remote-1/client SSH_ALIAS:/absolute/new/remote-1/observer.dylib "$LAB/results/m1-vt-1/"
scp SSH_ALIAS:/absolute/new/remote-2/client SSH_ALIAS:/absolute/new/remote-2/observer.dylib "$LAB/results/m1-vt-2/"
python3 "$E/audit.py" --runs "$LAB/results/m1-vt-1" "$LAB/results/m1-vt-2" \
  --reference /path/to/decoded.nv12 --out "$LAB/results/m1-vt-audit.json"
```

The audit is pinned to the observations and source hashes from the recorded
profile; a changed macOS service, selector path or hardware property requires a
new qualification. If remote completion cannot be established, the runner
leaves the laboratory reservation unresolved rather than assuming the device
is free.
