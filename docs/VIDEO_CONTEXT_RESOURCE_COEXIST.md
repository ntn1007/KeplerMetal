# Concurrent Metal resource and empty video context

On the pinned iMac, two signed, separate processes each created a public 4 MiB
shared Metal buffer, then created and released an empty native video-context
wrapper while that buffer remained alive. The context and the buffer's resource
field both matched the same Metal-created `IOAccelShared` object **during the
context lifetime**. In both processes, type-3 open, client association and
context connection release each returned zero; the context's 16 observed
wrapper slots stayed empty. The resource's shared pointer matched before and
after context release. All 4,194,304 buffer bytes matched the CPU pattern both
before context creation and after release.

Two same-executable controls created the buffer but did not create a context.
All four hosts rejected a deliberately null resource before the context probe,
without submitting a context request for that control. The hosts were
nonoverlapping and used the same cooperative GPU reservation. The
[audit record](video-context-resource-coexist-validation.json) includes hashes
and eight rejected mutations of results or process receipts. These mutations
are offline checks, not additional device tests.

This joins the earlier [empty-context observation](METAL_VIDEO_CONTEXT.md)
and [Metal resource identity observation](VIDEO_RESOURCE_IDENTITY.md) in the
same lifetime. It does **not** bind the Metal buffer to the video context, prove
that it is a valid video data buffer, validate resource teardown, run a GPU
kernel or demonstrate video decoding. The slots being empty are evidence of
that limited scope. The CPU pattern is not a GPU computation.

## Method and controls

The 4 MiB `MTLBuffer` is created and retained by ordinary Metal code. The
observer obtains the device and shared wrapper from Metal's normal constructor
path. Only after the buffer's resource field and its shared pointer pass the
pinned identity checks does the experiment request context creation. The
existing context-probe guard pins the code and six imported call targets,
calibrates local refusals, permits the previously qualified open, association
and release, and denies observed method/struct/scalar selectors on the probe
thread. No such selector was observed in the two context probes. Guard coverage
is bounded to these imports and the probing thread; it is not complete tracing
of framework or driver activity. Ordinary Metal initialization can perform its
own legitimate driver calls. The cooperative reservation does not exclude
WindowServer or unrelated processes.

The context is released before the buffer's final CPU comparison. The
experiment does not call the private Metal resource getter, retain the resource
pointer itself, or change the driver's management of either object. The
buffer's Objective-C lifetime is held through the final read. The previous
context and resource experiments remain unchanged. Two exploratory control and
coexistence processes with an earlier build are kept in the lab; they are not
included in the final four-host counts.

## Reproduction

Use the exact qualified profile, a verified `nvAccelerator` registry ID, the
common lab reservation root, and fresh paths. The `coexist` mode explicitly
creates and immediately releases the native empty context; `observe` is the
control. Both use the same frozen signed build.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified nvAccelerator registry ID>'
EXP=bridge/experiments/video_context_resource_coexist
(
  set -e
  python3 "$EXP/experiment.py" build --out "$LAB/results/coexist-build-new"
  for item in observe:1 coexist:1 observe:2 coexist:2; do
    mode=${item%:*}; n=${item#*:}
    python3 "$EXP/experiment.py" run --build "$LAB/results/coexist-build-new" \
      --out "$LAB/results/coexist-$mode-$n" --lab "$LAB" --registry-id "$RID" --mode "$mode"
  done
  python3 "$EXP/audit.py" --build "$LAB/results/coexist-build-new" \
    --runs "$LAB/results/coexist-observe-1" "$LAB/results/coexist-coexist-1" \
      "$LAB/results/coexist-observe-2" "$LAB/results/coexist-coexist-2" \
    --out "$LAB/results/coexist-audit-new.json"
)
```

The device, cache and kext profile checks are machine-specific. Signed binaries,
raw process receipts and private vendor code remain in the local lab; only
original experiment source and sanitized hashes are published. No system
component, OCLP setting or firmware was changed. The next question remains how
a legitimate client obtains a suitable video data buffer with a qualified
ownership and synchronization contract; the generic Metal buffer must not be
substituted for it based solely on this pointer match.
