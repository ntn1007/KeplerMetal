# First device-enumeration batch during a VideoToolbox request

A process-local, hardware-breakpoint witness observes the natural public
VideoToolbox session-creation path studied in
[VIDEO_VT_IMPORT_BINDING.md](VIDEO_VT_IMPORT_BINDING.md). On each of two
hardware-required requests, it sees a non-null result at the instruction
following the Metal enumeration import. A later stop on the same thread sees
return register `RAX = 1` following a call supplied with the selector
`countByEnumeratingWithState:objects:count:`; the list pointer held in `R12`
matches the earlier return. The selector and the complete 3,420-byte live
VideoToolbox function region were checked before setting the breakpoints.
The result is consistent with a **first batch of one element**.

The observation does **not** establish the complete list size or identify
that element as the GTX 880M. The indirect dispatch slot's live target was not
separately identified in this cohort, so the interpretation as an Objective-C
fast-enumeration count depends on that dispatch behaving as expected. No
Objective-C expression is evaluated by the debugger and no list element is
dereferenced. Debugger timing and bounded breakpoint coverage can affect or
miss behavior. Two hardware-required calls without the debugger also return
`-12906` and zero frames; this does not prove that the debugger has no other
effect. Both observed calls return the same status and zero frames.

Before the hardware cohort, a separate signed CPU program calibrated the
register witness with first-batch results 1 and 0 and a bad-marker refusal.
The first calibration attempt exposed a symbol-resolution defect and failed;
the corrected version passed in a fresh output directory. A separate early
Python address exploration also terminated with a segmentation fault; the
subsequent read used bounded Mach self-task reads. Neither was a GPU test.
Two debugged and two plain software controls decoded 24 frames matching
2,764,800 reference bytes; no matching hardware-path witness points fired in
the two software controls. Eight test runs used separate nonoverlapping
cooperative reservations and all debugger and target processes terminated.
The reservation does not exclude WindowServer.

[Audit](video-vt-first-enum-batch-validation.json) checks the signed binaries,
CPU calibration, cached function identity, loaded-code/selector checks
reported by the debugger, nonoverlapping receipts, binding snapshots, pixel
reference and debugger logs. The observed hardware debugger runs also emitted a
bounded VideoToolbox `-12906` diagnostic on stderr, which the audit verifies.
Five [offline mutations](video-vt-first-enum-batch-mutations.json) reject altered
batch, identity, arm, diagnostic and frame evidence; they execute no GPU work.
Three system-file hashes were checked before and after the runs; the display
inventory was checked at audit time. No system driver, framework, OCLP or
firmware was modified.

## Reproduction

Use the fixture and reference from [VIDEO_TRANSPORT.md](VIDEO_TRANSPORT.md), the
exact cache profile, the lab reservation and fresh paths. The debugger uses
hardware breakpoints in the test process and can affect timing.

```zsh
LAB='/path/to/nvidia-880m-lab/bridge'
CACHE='/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64'
E=bridge/experiments/video_vt_enumeration_witness
C="$LAB/results/vt-enum-cal-new"
B="$LAB/results/vt-enum-debug-build-new"
python3 "$E/calibrate.py" --out "$C"
python3 "$E/experiment.py" build --lab "$LAB" --calibration "$C" \
  --fixture /path/to/fixture --reference /path/to/decoded.nv12 --out "$B"
RUNS=()
for n in 1 2; do
  for mode in hardware software; do
    out="$LAB/results/vt-enum-$mode-debug-$n-new"
    python3 "$E/run.py" --lab "$LAB" --build "$B" --calibration "$C" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
  for mode in hardware-plain software-plain; do
    out="$LAB/results/vt-enum-$mode-$n-new"
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$out" || break 2
    RUNS+=("$out")
  done
done
python3 "$E/audit.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-enum-audit-new.json"
python3 "$E/mutations.py" --build "$B" --calibration "$C" --cache "$CACHE" --runs "${RUNS[@]}" --out "$LAB/results/vt-enum-mutations-new"
```

Next, qualify the live dispatch target and identify the element without
changing the video resource path. Neither hardware decoding nor a driver fix
has been demonstrated.
