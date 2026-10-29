# AppleGVA node free callsite: bounded runtime witness

A pinned AppleGVA code region has a path that unlinks an entry, moves its
address into the first argument register and calls a stub statically mapped to
`free` at image offset 150964. The dynamic target of that stub was not
independently traced. A hardware breakpoint on that call instruction was
resolved in two instrumented processes, each issuing three hardware-required
H.264 requests. It had **zero hits in both processes**.

Each process also observed one null property return in request window 1 and
four list-selection hits in windows 1, 1, 2 and 3. All six requests returned
`-12913` with zero images. A wrong-board control, a current-board run without
the witness, and three CPU software sessions with 18 reference-matching
frames were included. These requests use the previously described process-local
counterfactuals and the debugger may change timing.

**The absence at one callsite does not prove the allocation remained live.**
Another callsite, library, allocator path, unobserved interval, or address
reuse could explain later equal addresses. The request marker describes the
client window at the time of a stop; asynchronous causality remains unproved.
The witness compares the call argument with the previously recorded address if
the breakpoint fires; it neither invokes `free` nor changes the argument. Its
matching and different-address cases passed on an original CPU program with
hardware breakpoints. No comparison occurred at this callsite in the two
video processes because the breakpoint did not fire.

The [audit](video-gva-node-free-validation.json) binds the static capture,
separate stub mapping, CPU calibration and terminal run records. The source
region's live hash was checked by both the marker and debugger. No GPU video
execution, driver upgrade or performance improvement is established. No system
or OCLP component was modified.

The next step is to examine whether allocation and deallocation can be tracked
across the **actual allocator interfaces** with demonstrable coverage and a
positive control. A zero count from an unvalidated hook must not be presented
as proof that the node survived.

## Reproduction

Requires the retained pinned lab, static capture and shared cooperative GPU
reservation. Use fresh paths and do not restart while a target or debugger is
unresolved.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_node_free_witness
I="$R/gva-repeat-integrated-20261029-01"
C="$R/node-free-cal-new"
CTRL="$R/node-free-control-new"
B="$R/node-free-build-new"
python3 "$E/cpu_calibration.py" --out "$C"
python3 "$E/reserved_cpu.py" --lab "$LAB" --calibration "$C" --out "$CTRL"
python3 "$E/build_request.py" --lab "$LAB" --integrated "$I" --calibration "$C" --reserved-control "$CTRL" --out "$B"
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/node-free-cpu-new" --mode cpu --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/node-free-wrong-new" --mode wrong --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/node-free-off-new" --mode current --witness off
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/node-free-on1-new" --mode current --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/node-free-on2-new" --mode current --witness on
python3 "$E/audit_node_free.py" --base "$I/base" --build "$B" --calibration "$C" --reserved-control "$CTRL" \
 --region "$R/gva-stack-caller-20261028-01/function-region.private.bin" --mapping "$R/gva-stack-caller-stubs-20261028-01.json" \
 --runs "$R/node-free-cpu-new" "$R/node-free-wrong-new" "$R/node-free-off-new" "$R/node-free-on1-new" "$R/node-free-on2-new" \
 --out "$R/node-free-audit-new.json"
```
