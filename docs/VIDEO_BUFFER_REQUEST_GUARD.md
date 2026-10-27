# Real video wrapper, locally refused buffer request

On the pinned iMac profile, two signed, nonoverlapping processes created a real
empty native video-context wrapper from Metal's own `IOAccelShared` object,
while holding an ordinary 4 MiB Metal buffer. The experiment then called the
pinned user-mode `IOAccelVideoContextRequestDataBuffer` with class 0 and size
131,072 bytes. Its `IOConnectCallStructMethod` import reached a process-local
guard that checked and **refused** the request. The guard did not forward it
to IOKit or the GPU. The real wrapper returned the guard's refusal
`0xe00002e2`; all 16 context slots remained empty.

In each process the guard observed the selected real context port, selector 3,
an eight-byte input containing the two requested 32-bit values, and a 49-byte
output capacity. The latter matches 48 plus the independently read value 1 at
the qualified device object's offset `0x3c` on this profile. This is an
observation of **user-mode request preparation**, not evidence that the kernel
accepts those values or returns a 49-byte response. Context open, association
and release returned zero. The Metal buffer's CPU-checked bytes were unchanged
across the probe. Two controls used the same executable without creating a
context or attempting the request.

Before the guarded request, class 16 was rejected by the native user-mode
wrapper with `0xe00002c2` and no intercepted IOKit call. This demonstrates the
wrapper's checked bound only; it does not establish the valid kernel class
count. The request's class 0 and 128 KiB size come from two archived experiments
on a **historical 10.12.6 NVIDIA provider in a synthetic environment**. Those
experiments intercepted and refused the old provider's request and did not
validate these values on the current driver. Their hashes are checked by the
present audit; the related static provider analysis has REA evidence ID
`ev_63405699d0e72da770321c7d16abc6a5e7a87782cc37dc926f67eee412d21103`.

## Isolation and interpretation

Before creating the context, the experiment checks the qualified device,
shared-object and Metal resource relationships. The code pins the loaded
wrapper and callee hashes, context constructor, release path, and six
IOAccelerator import targets. Its guard is calibrated before use. On the probe
thread it permits only the already qualified context open, association and
release, refuses all method calls, and records the expected struct request
before returning the refusal. The output allocation is bounded to 4 KiB by a
preflight read of the device field. The guard does not write an invented
response. Two host results show one locally refused request apiece, no
unexpected guarded calls and no populated context slot.

The reservation is cooperative and does not exclude WindowServer. The guard
covers the checked imports on the probe thread, not every driver or process
path; ordinary Metal initialization can perform its own operations. The
experiment does not call the resource getter or bind the ordinary Metal buffer
to the video context. **No live selector-3 request, video buffer allocation,
GPU computation, video decode, or performance result is established.**

The [validation record](video-buffer-request-guard-validation.json) retains
source and result hashes and ten rejected offline audit mutations. Historical
results are separate from the four current processes. The prior static
[user-mode contract](VIDEO_BUFFER_USER_CONTRACT.md),
[kernel method analysis](VIDEO_METHOD_CONTRACT.md), and
[resource/context coexistence](VIDEO_CONTEXT_RESOURCE_COEXIST.md) remain
separate evidence. This experiment does not establish the private ABI for other
systems, sizes, classes, success paths, ownership or cleanup.

## Reproduction

Use the exact pinned profile, the shared lab reservation root, a verified GTX
`nvAccelerator` registry ID, and new output paths. `coexist` creates an empty
context and performs the locally refused user-mode request. `observe` is the
same-build control. The optional `--history` arguments verify the two retained
historical synthetic results; without them the audit reports that historical
provenance was not checked.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
RID='<verified nvAccelerator registry ID>'
EXP=bridge/experiments/video_buffer_request_guard
(
  set -e
  python3 "$EXP/experiment.py" build --out "$LAB/results/request-build-new"
  for item in observe:1 coexist:1 observe:2 coexist:2; do
    mode=${item%:*}; n=${item#*:}
    python3 "$EXP/experiment.py" run --build "$LAB/results/request-build-new" \
      --out "$LAB/results/request-$mode-$n" --lab "$LAB" --registry-id "$RID" --mode "$mode"
  done
  python3 "$EXP/audit.py" --build "$LAB/results/request-build-new" \
    --runs "$LAB/results/request-observe-1" "$LAB/results/request-coexist-1" \
      "$LAB/results/request-observe-2" "$LAB/results/request-coexist-2" \
    --history "$LAB/results/video-sierra-request-refused-positive-20261027-01/result.json" \
      "$LAB/results/video-sierra-request-refused-positive-20261027-02/result.json" \
    --out "$LAB/results/request-audit-new.json"
)
```

Vendor binaries, raw captures and signed hosts stay in the private lab. No
system driver, framework, OCLP configuration or firmware was changed. A real
request still requires an independently qualified kernel contract, output
layout, buffer ownership and cleanup; do not forward the request based on this
user-mode result alone.
