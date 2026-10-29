# Observed VideoToolbox IOKit call lengths on the iMac

This follow-up observes the naturally occurring public VideoToolbox path from
[the previous iMac cohort](VIDEO_IMAC_CLIENT_OBSERVER.md). The observer now
records the returned status, input structure length, output capacity and
returned length, plus a `dladdr` caller label and image-relative return address.
It forwards every call unchanged and does **not** read the contents of the
input or output buffers. Length pointers are read with bounded self-task Mach
reads; an unavailable read is represented as null rather than zero. Return
statuses are recorded even when their meaning is unknown.

Two hardware-required observed processes each produced these same six
`IOConnectCallStructMethod` observations before the public session create
failed with `-12906`:

| Connection type | Selector | Input bytes | Output capacity → reported bytes | Status | `dladdr` nearest caller |
| --- | ---: | ---: | --- | ---: | --- |
| 5 | 9 | 16 | no output-size pointer | 1 | `IOAccelDeviceCreateWithAPIProperty` |
| 5 | 2 | 0 | 600 → 600 | 0 | `IOAccelDeviceCreateWithAPIProperty` |
| 5 | 0 | 0 | 64 → 64 | 0 | `IOAccelDeviceCreateWithAPIProperty` |
| 5 | 7 | 0 | 24 → 24 | 0 | `IOAccelDeviceCreateWithAPIProperty` |
| 6 | 9 | 0 | 16 → 16 | 0 | `IOAccelSharedCreate` |
| 6 | 10 | 0 | 24 → 24 | 0 | `IOAccelSharedSetupDirtyRing` |

These are user-process call returns, **not** a kernel execution trace or a
video-buffer allocation. A null size pointer is not a zero-length result.
Values from type 5, type 6 and a possible video context must not be mixed.
`dladdr` reports the nearest symbol, and the service association uses the most
recent matching returned port name; neither establishes full object lifetime
or PCI ancestry. The observer's window, other-process, port-reuse and timing
limits from the earlier cohort remain in force.

## What the `1` does and does not show

The first row's return address is reported at image offset `0x1002` in a module
named `IOAccelerator`. Separately, the hash-pinned **on-disk** cache image has a
call to the `IOConnectCallStructMethod` import at offset `0xffd`, immediately
followed by a load of another register and then an overwrite of the return
register. The audit verifies the cache image UUID, the complete captured
function against the cache, the direct call target/import and both instructions
using a private disassembly. Conditional on the loaded code matching that
on-disk image, this path does not test that return value before overwriting it.
The live function bytes and live import target were not hashed here. Later
type-5 and type-6 calls returned zero in the same recorded process.

This narrows the investigation: the value `1` must not be presented as the
demonstrated cause of `-12906`. It also does not prove that the request had no
side effects, that every later path is valid, or that another component did not
use the result. The complete reason for the public session failure remains
unresolved. No data-buffer selector was fabricated or forwarded by the probe.

## Validation and reproduction

The observer was separately calibrated against **three null-port calls** to
the three monitored IOKit method forms. It compared the actual returned status
and caller-side lengths with the observer's recorded fields; no GPU connection
was opened. The main cohort comprises eight signed, serialized processes:
four software controls produced 24 frames matching 2,764,800 FFmpeg reference
bytes, and four hardware-required creates returned `-12906` and zero frames.
The two plain and two observed runs agree on each outcome. Calibration and
observations are separately linked in [the audit](video-imac-call-contract-validation.json).
Three [offline mutations](video-imac-call-contract-mutations.json) of selector,
create status and returned length were rejected after output hashes were
recomputed. They do not represent additional GPU runs.

The build checks three pinned system files before and after each process; the
auditor checks two kernel-extension files and the PCI display inventory at
audit time, not loaded kernel bytes. The cooperative reservation does not
exclude WindowServer. Vendor binary captures and signed executables remain in
the local lab. No system driver, framework, OCLP setting or firmware was changed.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/video_imac_call_contract
B="$LAB/results/call-contract-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --fixture /path/to/fixture \
  --reference /path/to/decoded.nv12 --out "$B"
python3 "$E/calibrate.py" --build "$B" --out "$LAB/results/call-calibration-new"
for n in 1 2; do
  for mode in software-plain hardware-observed software-observed hardware-plain; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" \
      --out "$LAB/results/call-$mode-$n-new" || break 2
  done
done
python3 "$E/audit.py" --build "$B" --m1-audit docs/video-m1-client-observer-validation.json \
  --cache /System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64 \
  --device-capture "$LAB/results/ioaccel-device-create-static-20261027-01" \
  --calibration "$LAB/results/call-calibration-new" --work "$LAB/results/call-audit-work-new" \
  --runs "$LAB/results/call-software-plain-1-new" "$LAB/results/call-hardware-observed-1-new" \
    "$LAB/results/call-software-observed-1-new" "$LAB/results/call-hardware-plain-1-new" \
    "$LAB/results/call-software-plain-2-new" "$LAB/results/call-hardware-observed-2-new" \
    "$LAB/results/call-software-observed-2-new" "$LAB/results/call-hardware-plain-2-new" \
  --out "$LAB/results/call-audit-new.json"
```

The exact device capture is a private, hash-checked input. A changed macOS
cache or SDK profile requires fresh qualification. No hardware video decode,
transparent Metal integration or performance gain is established.
