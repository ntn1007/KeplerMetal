# Public VideoToolbox client on the iMac

Eight signed, nonoverlapping processes tested the same six-frame H.264 fixture
used in the [M1 reference](VIDEO_M1_CLIENT_OBSERVER.md). On the iMac, two plain
and two observed software sessions each decoded six frames: all **24 frames,
2,764,800 active NV12 bytes**, matched the pinned FFmpeg software reference.
The sessions explicitly disabled hardware; the optional hardware-property query
returned `-12900` and no value and is not treated as false.

Two plain and two observed hardware-required sessions all failed during
`VTDecompressionSessionCreate` with **`-12906`**, before producing a frame.
The diagnostic host's exit code zero indicates that this failure was recorded
successfully; it does **not** mean hardware decoding passed. This unmodified
public path is distinct from earlier process-local policy experiments that
returned `-12913`.

## Bounded calls observed

The observer is the same process-local interposer used for the M1 reference.
It forwards its declared `IOServiceOpen` and `IOConnectCall*` imports and
queries class/name metadata after successful opens. A null-port calibration
checks its host binding without sending a request to a device. During each
hardware-required run it recorded opens for `IOSurfaceRoot`, `nvAccelerator`
type 5 and `nvAccelerator` type 6. Correlating by the most recent returned port
name, the recorded `IOConnectCallStructMethod` values were:

| Observed connection type | Selector values |
| --- | --- |
| 5 | 9, 2, 0, 7 |
| 6 | 9, 10 |

Those numbers are **not interchangeable between connection types**. The two
observed software runs recorded only the IOSurfaceRoot open and its calls.
The hardware observation ends after the failed create; the software window
also includes decode and output copying, so event counts are not a performance
or one-for-one call comparison.

No type-3 open appeared through the monitored import in these two hardware
windows. This is a bounded negative observation, not proof that no other code
or process opened one, that the old NVIDIA provider is unreachable, or that
any particular observed call caused the failure. The observer does not cover
all dyld bindings, direct traps, other processes or firmware; its counters and
event snapshot are not atomic across all threads. Port-name reuse and lifetime
can affect association. The service's PCI ancestor was not independently
resolved in this witness, and the calls' kernel dispatch and semantics were not
traced. No synthetic private selector or video command was sent.

## Evidence

The [auditor](video-imac-client-observer-validation.json) rechecks the frozen
source, signed host and library, raw output, reference pixels, observer
calibration, service associations, eight terminal reservations and
nonoverlapping intervals. Two [offline mutations](video-imac-client-observer-mutations.json)
changed a selector or failure code and recomputed the raw-output hash; the
auditor rejected each for the intended reason. The original evidence was
unchanged. These mutations are not additional hardware tests.

Three existing system-file hashes were checked before and after each process.
At audit time, separate on-disk hashes matched the pinned GeForce and
IOAcceleratorFamily2 images; the display inventory reported NVIDIA PCI
`10de:1198`, 8 GB, and macOS 26.7.1 build 25G241. These are audit-time file and
inventory facts, not a hash of loaded kernel memory or a per-process PCI
identity proof. The cooperative reservation does not exclude WindowServer.
No system driver, OCLP, firmware or protected configuration was modified.

## Reproduction

Obtain the pinned fixture and reference described in [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md).
Use the existing lab reservation and fresh paths. A changed profile or source
is refused instead of silently repinned. The client records a failed session as
`CREATE_FAILED`; do not interpret its diagnostic process exit as decoder success.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/video_imac_client_observer
B="$LAB/results/imac-vt-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --fixture /path/to/fixture \
  --reference /path/to/decoded.nv12 --out "$B"
for n in 1 2; do
  for mode in software-plain hardware-observed software-observed hardware-plain; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" \
      --out "$LAB/results/imac-vt-$mode-$n-new" || break 2
  done
done
python3 "$E/audit.py" --build "$B" --m1-audit docs/video-m1-client-observer-validation.json \
  --runs "$LAB/results/imac-vt-software-plain-1-new" "$LAB/results/imac-vt-hardware-observed-1-new" \
    "$LAB/results/imac-vt-software-observed-1-new" "$LAB/results/imac-vt-hardware-plain-1-new" \
    "$LAB/results/imac-vt-software-plain-2-new" "$LAB/results/imac-vt-hardware-observed-2-new" \
    "$LAB/results/imac-vt-software-observed-2-new" "$LAB/results/imac-vt-hardware-plain-2-new" \
  --out "$LAB/results/imac-vt-audit-new.json"
```

The fixture, signed hosts, full captures and vendor binaries stay in the local
lab. The next step is to qualify a legitimate NVIDIA data-buffer producer and
its ownership and returned mapping; the observations above do not authorize a
new private request or prove a working video channel.
