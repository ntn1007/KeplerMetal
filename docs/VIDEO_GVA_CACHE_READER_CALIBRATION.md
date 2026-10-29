# Cache witness reader: CPU hardware-breakpoint calibration

A standalone original CPU program exercised the **same Python callback** used
in the [earlier AppleGVA video witness](VIDEO_GVA_CACHE_WITNESS.md). A real
hardware breakpoint fired four times, on the same thread, with pinned target
instruction bytes. The callback observed:

| Synthetic node | Read valid | First byte nonzero | Flag byte |
| --- | --- | --- | --- |
| Nonempty, flag clear | yes | yes | 0 |
| Empty, flag set | yes | no | 1 |
| Nonempty, flag set | yes | yes | 1 |
| Unreadable pointer | no | no reported | 0 reported |

The values for the unreadable pointer are defaults, not data read from the
node. A separate process with a deliberately incorrect base was refused before
arming the test breakpoint. Both processes exited normally. The audit binds
the callback's SHA-256 to the previous video build; the source used in these
CPU tests is the exact callback from that build.

The initial two calibration attempts failed before the test breakpoint was
armed because the assembler symbol did not resolve as an LLDB `SBFunction`;
the successful implementation falls back to its `SBSymbol` address. Failed
outputs remain in the private laboratory. No GPU or vendor program was run.
This test does not prove that the cache branch was reached in the earlier
video processes: it was **not** reached there. It does not validate NVIDIA
codec strings, node lifetime, hardware decoding, or the complete debugger
behavior on all threads. It establishes the reader's behavior on these four
controlled CPU cases, using a real breakpoint rather than a mocked process.

[Sanitized audit](video-gva-cache-reader-calibration.json) ·
[Static cache path](VIDEO_GVA_CACHED_CODEC.md)

## Reproduction

```bash
R='/path/to/nvidia-880m-lab/bridge/results'
E=bridge/experiments/video_gva_cache_reader_calibration
python3 "$E/calibrate.py" --out "$R/cache-reader-cal-new"
python3 "$E/audit.py" --calibration "$R/cache-reader-cal-new" \
  --video-build "$R/gva-cache-hw-build-20261029-01" \
  --out "$R/cache-reader-audit-new.json"
```

Inputs are built in a new directory, signed ad hoc with `get-task-allow` for
the own-process debugger, and never installed. The audit requires the retained
previous private video build and exact matching witness source. It verifies
source and artifact hashes and refuses an existing output path.
