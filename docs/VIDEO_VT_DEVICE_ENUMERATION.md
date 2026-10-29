# Public Metal device-enumeration interposition during VideoToolbox setup

This experiment tests whether a process-local `DYLD_INTERPOSE` observer can
capture the return values of `MTLCopyAllDevices` and
`MTLCopyAllDevicesWithObserver` during public VideoToolbox session creation.
The observer forwards the caller's arguments and original retained return value
unchanged; it counts calls, returned devices, and devices whose public
`registryID` matches the uniquely selected NVIDIA `nvAccelerator`. It reports
counts only, retaining neither the objects beyond the hook nor registry IDs. No private video
method or manufactured context is used.

In two observed public Metal controls, the client deliberately calls both
functions. The observer sees one call to each, one returned device per call,
and one registry-ID match. Independently in those same controls and in two
plain controls, the client follows each returned device's public registry entry
to a PCI ancestor and confirms the unique target `10de:1198`. These positive
controls validate interception of the client's own direct calls; they do not
establish coverage of calls made by other frameworks.

During two observed hardware-required VideoToolbox requests, the existing
constructor observer confirms the selected device and shared-object events,
but neither enumeration interposition hook records a call. Both observed and
two plain hardware-required sessions return `-12906` and zero images. Four
software sessions decode 24 frames matching 2,764,800 reference bytes. No
matching constructors or enumeration interpositions were observed in the two
software windows. Metal control checks are CPU-side and do not establish GPU
dispatch or hardware decode.

The earlier [stack experiment](VIDEO_VT_OBJECT_STACKS.md) reported a MetalOld
return address whose nearest symbol is `MTLCopyAllDevicesWithObserver` during
a separate VideoToolbox cohort. The present absence of an interposed event
**does not prove** that VideoToolbox did not enumerate the GTX, nor does it
prove why this interception missed the path. The earlier `dladdr` label is a
nearest symbol, and neither call target nor coverage of the framework's
binding was validated here. Returned enumeration contents and the cause of
`-12906` remain unknown. The observer may miss uninstrumented bindings,
earlier events, other threads or processes, and can affect timing.

The twelve signed processes used nonoverlapping cooperative reservations and
terminal receipts; WindowServer is not excluded. The [audit](video-vt-device-enumeration-validation.json)
checks the build, signatures, source and result hashes, PCI profile, positive
controls, pixel data, object linkage and per-mode event counts. Seven
[offline mutations](video-vt-device-enumeration-mutations.json) verify rejection
of altered data; they are not additional GPU runs. Three system-file hashes
were checked before and after each run, with two kernel-extension file hashes
and display inventory checked at audit time, not as loaded-kernel bytes. No
system driver, framework, OCLP or firmware was changed.

## Reproduction

Use the fixture and reference described in [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md)
and the lab's pinned reservation. Supply fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/video_vt_device_enumeration
B="$LAB/results/vt-enum-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --fixture /path/to/fixture \
  --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in metal-observed hardware-observed metal-plain software-observed hardware-plain software-plain; do
    out="$LAB/results/vt-enum-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --runs "${RUNS[@]}" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-enum-audit-new.json"
python3 "$E/mutations.py" --build "$B" --runs "${RUNS[@]}" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-enum-mutations-new"
```

A next experiment must independently validate the actual caller and binding,
or observe the returned list through a qualified alternative path. No change
in driver behavior or acceleration has been demonstrated.
