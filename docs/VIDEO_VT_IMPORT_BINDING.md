# VideoToolbox's Metal enumeration import

The preceding [interposition study](VIDEO_VT_DEVICE_ENUMERATION.md) saw direct
client calls to the public Metal enumeration APIs but no corresponding hook
invocation in two hardware-required VideoToolbox processes. This follow-up
examines the specific return address recorded by the earlier
[stack cohort](VIDEO_VT_OBJECT_STACKS.md), without modifying a system component.

On the pinned x86_64 cache image, the return address `VideoToolbox+0x5fd9fb`
follows a five-byte direct call at `+0x5fd9f6`. The cache's import metadata
identifies the destination stub as `_MTLCopyAllDevicesWithObserver`. The
containing bounded function region is selected by `LC_FUNCTION_STARTS`; its
exact source-level identity is not asserted. The audit verifies the cache image
UUID, the call and stub hashes, the decoded stub and slot addresses, and the
function-region hash. The private code capture and disassembly are not
published.

In each of 12 new signed processes, the test client reads its own loaded call
and stub bytes through bounded `mach_vm_read_overwrite` operations and checks
their hashes against the cache. It then reads the stub's pointer slot and uses
`dladdr` to describe its target. Both before and after the test window, the
slot points to `MetalOld.dylib+0x29996`, whose nearest symbol is
`MTLCopyAllDevicesWithObserver`. This holds in both observed hardware-required
processes, even though their injected observer recorded no enumeration hook
call; the direct Metal client controls still hit both hooks. A read-only REA
Mach-O inspection independently identified `_MTLCopyAllDevicesWithObserver`
as an export at `0x29996` in the on-disk `MetalOld.dylib`, SHA-256
`fd1e8e07491819334a1b3e788f01bc0d4fef0229c1022cb2fc29031c5c5dc97e`
(Evidence `ev_e35d12e93d68c871e2fe84de911c621e254067a0f10b19f733c798165ce735b3`).

These observations strongly support a binding path that bypasses the direct
client's interposition hook. The slot was sampled **before and after**, not at
the instant of the VideoToolbox call; the previous stack and this cohort are
separate runs. Only the live five-byte call and six-byte stub are checked, not
the live target's implementation. The result does not prove the returned
device list, why `-12906` occurs, or execution of a hardware decoder. Symbol
labels and bounded stack unwinding retain their earlier limitations.

The two observed and two plain hardware-required requests returned `-12906`
and zero frames. Four software sessions matched 24 frames and 2,764,800
reference bytes. Two observed and two plain Metal controls independently
matched both enumeration lists to the unique `10de:1198` PCI ancestor; their
buffer checks are CPU-side. No extra video selector or synthetic video context
is used. The twelve signed processes had nonoverlapping cooperative GPU
reservations and terminal receipts; WindowServer was not excluded.

The [audit](video-vt-import-binding-validation.json) verifies the cached call,
function and import plus signed binaries, hashes, profiles, controls, pixels,
and the before/after snapshots. Eight [offline mutations](video-vt-import-binding-mutations.json)
exercise negative checks and do not represent additional GPU runs. Three
system files were checked before and after each run; two kernel-extension
files and MetalOld's on-disk file were hashed at audit time, not as loaded
kernel or function bytes. No system driver, framework, OCLP or firmware was
changed.

## Reproduction

Use the fixture and reference in [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md) and
the lab's pinned cooperative reservation. The cache must match the audited
profile; use fresh output paths.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_enumeration_binding
B="$LAB/results/vt-binding-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --fixture /path/to/fixture \
  --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in metal-observed hardware-observed metal-plain software-observed hardware-plain software-plain; do
    out="$LAB/results/vt-binding-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --runs "${RUNS[@]}" --cache "$CACHE" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-binding-audit-new.json"
python3 "$E/mutations.py" --build "$B" --runs "${RUNS[@]}" --cache "$CACHE" \
  --m1-audit docs/video-m1-client-observer-validation.json --out "$LAB/results/vt-binding-mutations-new"
```

A further experiment needs an independently qualified observation at or after
the actual call to determine the list VideoToolbox receives. This is an
instrumentation finding, not a hardware-video or driver fix.
