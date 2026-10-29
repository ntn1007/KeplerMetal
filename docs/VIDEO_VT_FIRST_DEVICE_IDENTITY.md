# NVIDIA device identity in VideoToolbox's first enumeration batch

Two hardware-required VideoToolbox session-creation attempts reached the
Metal enumeration path from [the previous witness](VIDEO_VT_FIRST_ENUM_BATCH.md).
In each, a debugger observed a successful registry-ID write in the naturally
constructed Metal device, a non-null returned list, and a first enumeration
batch of one element. The first list element was the **same object** as the
constructed device whose registry ID matched the uniquely selected
`nvAccelerator` with PCI ancestor `10de:1198`.

This establishes a bounded identity relationship for the first element in the
observed processes: VideoToolbox's enumeration path receives an object linked
to the GTX 880M. It does not establish that this is the only element in the
complete list, that a decoder selects or retains it, that the video engines
run, or why the public session create returns `-12906`.

## Method and controls

The host selects the target by traversing the public IOKit PCI ancestry and
passes the selected registry ID to a no-op marker immediately before the
public VideoToolbox call. At a hardware breakpoint after the natural
registry-ID call, the debugger reads the constructed device pointer and its
registry field, retaining only a per-thread match in the debugger's memory.
At a later breakpoint it reads the first pointer in the fast-enumeration item
buffer and compares it with the saved device pointer. Raw object pointers and
registry IDs are not emitted. No new video selector, artificial video context,
or debugger expression is executed.

Before arming, the debugger verifies loaded VideoToolbox and MetalOld image
UUIDs, hashes of the relevant live instruction regions, the live selector
`countByEnumeratingWithState:objects:count:`, and an indirect dispatch target
resolved to the `objc_msgSend` symbol. The dispatch target is sampled at
arming, not at the later call itself. At the device stop it reads the
profile-pinned instance-variable offset after class initialization; the
instance-variable value can differ earlier in the process. The audit checks
that the pinned on-disk MetalOld instructions and import table name
`IORegistryEntryGetRegistryEntryID`; it does not separately observe the live
binding of that call.

A separate CPU calibration exercises first-batch values one and zero, a wrong
marker, and a wrong registry ID. The wrong ID yields a nonmatching device and
item. Two initial hardware witness attempts ended cleanly without arming:
the offset check incorrectly assumed a small fixed value before Objective-C
class initialization. The corrected witness samples the offset at the device
stop, is recalibrated in a fresh directory, and produced the results above.

Two observed and two unobserved hardware-required calls all return `-12906`
and zero frames. Two observed and two plain software controls decode 24 frames
matching 2,764,800 reference bytes; neither debugged software control hits the
hardware-path witness points. The eight serialized test runs use separate
cooperative reservations and all debugger and target processes terminate.
WindowServer is not excluded. The debugger may change timing and these checks
do not prove that the observed code is the only possible path.

The [audit](video-vt-first-device-identity-validation.json) verifies the
calibration, signed build, source and result hashes, cached and on-disk code
profiles, debugger observations, receipts, timing intervals and software
pixels. It checks the expected VideoToolbox diagnostic emitted on stderr by
the observed hardware requests. Seven [offline mutations](video-vt-first-device-identity-mutations.json)
test rejection of altered batch, list, first-item, device, arming, diagnostic
and frame evidence; they execute no GPU work. Three system-file hashes were
checked before and after each run; the MetalOld file and display inventory
were checked at audit time. No system driver, framework, OCLP or firmware was
modified.

## Reproduction

Use the fixture and reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md),
the pinned cache and cooperative reservation, and fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_enum_identity
C="$LAB/results/vt-identity-cal-new"
B="$LAB/results/vt-identity-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-identity-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-identity-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-identity-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-identity-mutations-new"
```

The next investigation should follow the device through the subsequent
VideoToolbox filtering and decoder creation, with separate positive and
negative controls. This result is not a hardware-video or driver fix.
