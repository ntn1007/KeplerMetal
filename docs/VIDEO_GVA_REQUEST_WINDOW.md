# AppleGVA observations during three request windows

Two instrumented processes each issued three hardware-required H.264 requests
with the same process-local dependency and board-policy counterfactuals. A
client-owned request marker was read by LLDB at each observed breakpoint:

| Request window | Property-return hits | List-selection hits |
| --- | ---: | ---: |
| 1 | 1 | 2 |
| 2 | 0 | 1 |
| 3 | 0 | 1 |

Both runs gave this sequence; the property return was null, and all three
requests returned `-12913` and zero images. The cached-byte-check breakpoint
was resolved and had zero hits in each process. A wrong-board control returned
`-12906` three times without these hits. A no-marker current-board control
returned `-12913` three times. A separate CPU run produced 18 frames matching
2,073,600 reference bytes. Every target and debugger terminated and its lab
reservation reached terminal state.

The marker denotes which synchronous client request was in progress when the
process stopped; it **does not prove the cause of an asynchronous callback**.
The callback threads differed between the first and later list observations.
A matching address still does not prove object lifetime or rule out free and
reuse. The recorded property count does not establish what happens outside
the armed breakpoint interval or in other configurations. The debugger and
counterfactuals can affect behavior. No NVIDIA codec value or hardware-video
execution is established.

The marker reader was calibrated at hardware breakpoints in an original CPU
program for windows 1, 2 and 3, and for arming while window 1 was already
active; invalid base and pointer controls were retained. An earlier wrong-board
attempt incorrectly required the window to be zero at arm time and was
rejected: AppleGVA loaded while request 1 was active. That failed run remains
in the private lab and is not included in the five qualified runs.

The [sanitized audit](video-gva-request-window-validation.json) binds the
calibration, build, per-request records and frame hashes. No system driver,
OCLP or firmware was changed. The next step is to distinguish persistent
allocation from address reuse with a bounded lifetime witness before drawing
conclusions about cached nodes.

## Reproduction

Requires the existing integrated private laboratory build and shared GPU
reservation. Use fresh paths and wait for terminal state after each run; do
not restart while a child or debugger outcome is unresolved.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_request_witness
I="$R/gva-repeat-integrated-20261029-01"
C="$R/request-cal-new"
CTRL="$R/request-control-new"
B="$R/request-build-new"
python3 "$E/cpu_calibration.py" --out "$C"
python3 "$E/reserved_cpu.py" --lab "$LAB" --calibration "$C" --out "$CTRL"
python3 "$E/build_request.py" --lab "$LAB" --integrated "$I" --calibration "$C" --reserved-control "$CTRL" --out "$B"
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/request-cpu-new" --mode cpu --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/request-wrong-new" --mode wrong --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/request-off-new" --mode current --witness off
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/request-on1-new" --mode current --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/request-on2-new" --mode current --witness on
python3 "$E/audit_request.py" --base "$I/base" --build "$B" --calibration "$C" --reserved-control "$CTRL" \
 --runs "$R/request-cpu-new" "$R/request-wrong-new" "$R/request-off-new" "$R/request-on1-new" "$R/request-on2-new" --out "$R/request-audit-new.json"
```
