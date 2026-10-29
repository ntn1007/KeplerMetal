# Callers of the device and shared constructors during VideoToolbox setup

A follow-up to [the object observation](VIDEO_VT_OBJECT_OBSERVER.md) records
`dladdr` labels and image-relative return addresses for the naturally occurring
constructor calls in the selected NVIDIA process-local observation window.
Two observed hardware-required VideoToolbox requests and two observed public
Metal controls each show the same addresses:

| Constructor | Image | Return offset | Nearest `dladdr` symbol |
| --- | --- | ---: | --- |
| `IOAccelDeviceCreateWithAPIProperty` | `MetalOld.dylib` | `0x1d11` | `-[MTLIOAccelDevice initWithAcceleratorPort:]` |
| `IOAccelSharedCreate` | `MetalOld.dylib` | `0xb4679` | `-[MTLIOAccelDevice lazyInitialize]` |

These are nearest-symbol labels for the immediate return addresses, not a
complete stack trace. The observer does not identify the original caller or
thread that initiated Metal setup, establish a causal relationship with
VideoToolbox, hash the live caller instructions, or prove that a video
decoder consumed these objects. Its active window includes work outside the
public session-creation call. It forwards the original calls, does not retain
these objects, and makes no private configuration call or fabricated video
request. As with the earlier observer it may miss other bindings or processes;
the shared reservation does not exclude WindowServer.

The two observed and two unobserved hardware-required sessions all still
failed with `-12906`, yielding no images. Four software sessions decoded 24
frames matching 2,764,800 reference bytes. Two observed and two plain Metal
controls passed their CPU-side shared-buffer checks; they are not GPU dispatch
or hardware-video tests. No constructor caller was recorded in the two
software-observed windows. All twelve signed processes had distinct,
nonoverlapping cooperative reservations and terminal receipts.

[Audit](video-vt-object-callers-validation.json) checks signed binary copies,
source and build hashes, profile, result provenance, pixels, object type and
link, and the pinned caller labels. [Mutation tests](video-vt-object-callers-mutations.json)
check rejection of altered caller image or offset, and altered shared link,
device type, configuration-call count or status. These are offline tests,
not new GPU executions. Three system-file hashes were checked before and after
each process; two kernel-extension file hashes and GPU inventory were checked
at audit time, not as loaded kernel bytes. No system driver, framework, OCLP or
firmware was changed.

## Reproduction

Run from the repository root with the fixture and reference described in
[VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md). The harness uses the laboratory's
pinned cooperative reservation and requires a fresh path for every output.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/video_vt_object_callers
B="$LAB/results/vt-callers-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --fixture /path/to/fixture \
  --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in metal-observed hardware-observed metal-plain software-observed hardware-plain software-plain; do
    out="$LAB/results/vt-callers-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --runs "${RUNS[@]}" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-callers-audit-new.json"
python3 "$E/mutations.py" --build "$B" --runs "${RUNS[@]}" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-callers-mutations-new"
```

The next useful step is to observe the caller chain and decision around this
Metal initialization in the natural video path, then establish which component
returns the video error. A matching Metal caller is evidence of common setup,
not working hardware decode or a driver improvement.
