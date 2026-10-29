# Scoped tracking of the AppleGVA node address

In two instrumented processes, LLDB captured the node address at the pinned
`IOGVACodec` property-return breakpoint and wrote it into an exported variable
of **our own injected observer**. It did not write the AppleGVA node or vendor
code. The observer was explicitly armed by our client. At four subsequent
list-selection stops, during request windows 1, 1, 2 and 3, both observed
matching `free` and `malloc_zone_free` counters were **zero**. The client
still received `-12913` and zero images for each of its three hardware-required
requests.

The AppleGVA free-call slot mapped in the prior audit pointed to the observer
at arming and at each list stop. A separate CPU calibration used the same
observer and debugger write mechanism with an independently built caller:
a watched free was counted, an unrelated free was excluded, and reversing
the order produced the expected results. A wrong-board control, a
current-board run without the watcher, and three CPU software sessions with
18 matching frames were also checked. Every qualified process and its debugger
terminated; their cooperative reservations reached terminal state.

**This is not proof that the node remained allocated.** Coverage is limited
to calls actually interposed by these two interfaces, from the pointer handoff
through the last observed list stop. Other allocators, direct or hidden calls,
free and reuse before handoff, events after the last stop, and later binding
changes are not excluded. The zero counter applies to a pointer value; it does
not establish object identity or explain why the decoder fails. The debugger
can alter timing, and the requests retain process-local counterfactuals.
No hardware video or performance improvement is established.

An initial CPU-only variant tried to arm from a library constructor and failed
with a mutex-initialization error; it was not used for video. The retained
variant arms explicitly from our client after startup. No system driver,
framework, OCLP or firmware was changed. The [sanitized audit](video-gva-heap-track-validation.json)
binds the calibration, pinned static free mapping, signed build, frame files
and terminal run records.

The next useful investigation is to identify additional allocator routes or
validate an independent lifetime signal; neither a matching address nor this
bounded zero count alone establishes continued allocation.

## Reproduction

Requires the prior private integrated/request builds, pinned AppleGVA capture,
and the shared cooperative reservation. Use fresh paths; if a target or
debugger outcome is unknown, retain the reservation and inspect it.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_heap_track
I="$R/gva-repeat-integrated-20261029-01"
P="$R/gva-request-build-20261029-02"
C="$R/heap-track-cal-new"
B="$R/heap-track-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/build_video.py" --lab "$LAB" --parent "$P" --heap-calibration "$C" --out "$B"
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-track-cpu-new" --mode cpu --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-track-wrong-new" --mode wrong --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-track-off-new" --mode current --witness off
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-track-on1-new" --mode current --witness on
python3 "$E/run_gva.py" --lab "$LAB" --base "$I/base" --build "$B" --out "$R/heap-track-on2-new" --mode current --witness on
python3 "$E/audit.py" --base "$I/base" --build "$B" --heap-calibration "$C" \
 --region "$R/gva-stack-caller-20261028-01/function-region.private.bin" --mapping "$R/gva-stack-caller-stubs-20261028-01.json" \
 --metadata "$R/gva-stack-caller-20261028-01/metadata.json" \
 --runs "$R/heap-track-cpu-new" "$R/heap-track-wrong-new" "$R/heap-track-off-new" "$R/heap-track-on1-new" "$R/heap-track-on2-new" --out "$R/heap-track-audit-new.json"
```
