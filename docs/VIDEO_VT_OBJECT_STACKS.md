# VideoToolbox and Metal constructor stacks

In a follow-up to [the immediate-caller study](VIDEO_VT_OBJECT_CALLERS.md),
the observer captures at most 32 same-thread return addresses with `backtrace`
inside each intercepted constructor, before forwarding the original call.
`dladdr` resolves image-relative addresses and nearest symbols; raw virtual
addresses and complete paths are not reported. The bounded capture is kept
only for calls matching the selected NVIDIA service/device. No device or
video context is invented, and no extra video method is called.

In both observed hardware-required processes, the device and shared-object
constructor stacks were on the process main thread. Each contained, in this
order, return addresses in `MetalOld.dylib` at `0x29a8f` and in VideoToolbox at
`0x5fd9fb`, `0x3ff3`, `0x5ff59e`, `0x4e7d`, and `0x1c98c`. The nearest
`dladdr` labels for the last two are `VTDecompressionSessionCreateWithOptions`
and `VTDecompressionSessionCreate`, respectively; the Metal return is labelled
`MTLCopyAllDevicesWithObserver`. Each captured stack reached the test client's
`main`. This ties the observed Metal initialization to the active public
VideoToolbox session-creation call on that thread. Two observed Metal controls
instead contain `MTLCreateSystemDefaultDevice` at `0x14fe0` before the test
client, with the same immediate constructor callers as the video runs.

The labels are nearest exported symbols, not verified function boundaries;
optimized unwinding can omit inlined or tail-called frames. The live caller
instructions and unwind correctness were not independently validated. The
stack is bounded, process-local, and may miss other threads, earlier work,
other bindings or other processes. It does not prove which later component
uses these objects, what any undocumented argument means, or why the video
request fails. The observer itself adds instrumentation and can affect timing.

Two observed and two plain hardware-required creates all returned `-12906`
with zero images. Two observed and two plain software sessions decoded 24
frames matching 2,764,800 reference bytes. Two observed and two plain Metal
controls passed CPU-side shared-buffer checks; they are not GPU dispatch or
hardware decode tests. No matching constructors were captured during the two
software-observed windows. The 12 signed processes used separate,
nonoverlapping cooperative reservations and terminal receipts. The reservation
does not exclude WindowServer.

[Audit](video-vt-object-stacks-validation.json) checks build and result hashes,
signatures, target profile, exact software pixels, object types and links,
main-thread indication, a capture shorter than the 32-frame limit, and the ordered
image-relative stack subsequences. [Seven offline mutations](video-vt-object-stacks-mutations.json)
exercise rejection of altered object links, types, safety counts, status,
immediate callers and a stack address. They are not new GPU runs. Three system
files were hashed before and after each run; two kernel-extension files and the
GPU inventory were checked at audit time, not as loaded kernel bytes. No system
driver, framework, OCLP or firmware was changed.

## Reproduction

Use the fixture and reference described in [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md)
and a fresh output for each run. The harness uses the lab's pinned cooperative
reservation.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/video_vt_object_stacks
B="$LAB/results/vt-stacks-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --fixture /path/to/fixture \
  --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in metal-observed hardware-observed metal-plain software-observed hardware-plain software-plain; do
    out="$LAB/results/vt-stacks-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --runs "${RUNS[@]}" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-stacks-audit-new.json"
python3 "$E/mutations.py" --build "$B" --runs "${RUNS[@]}" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-stacks-mutations-new"
```

Next, investigate the decision following device enumeration on the public
VideoToolbox path using separately qualified observation. A stack alone does
not establish hardware decode or a driver fix.
