# Hardware-breakpoint witness: CPU calibration

An original x86_64 test program dynamically loads an original marker library.
LLDB resolves a pending **hardware** breakpoint on that marker; a debugger
callback then sets two additional auto-continuing hardware breakpoints. The
two controlled functions each reach their breakpoint once and their eight
observed code bytes match the values read before arming. The program produces
22 and exits normally. A deliberately incorrect marker argument is refused;
the program still completes and neither target breakpoint fires.

This checks the proposed mechanism on a CPU-only program. It does **not** prove
that the AppleGVA constructor returns, that a video engine executes, or that
the debugger's process-local observation is behaviorally transparent. The
calibration host alone has an ad hoc `get-task-allow` entitlement; it changes
no system entitlement or service. No vendor program or GPU workload ran.

The experimental [debugger callback](../bridge/experiments/video_gva_hw_witness/lldb_witness.py)
also contains an AppleGVA profile that checks three live code-region hashes
before arming. The separate marker source checks the pinned image UUID and the
same hashes. **That profile has not been executed against AppleGVA.** The
marker was compiled, but its activation and lifecycle have not been qualified
in a video process. In particular, it must not be launched against the GPU
until a runner retains the shared reservation across the debugger and its
child, handles debugger stops without killing the child, and establishes their
terminal identities. A CPU calibration is not such a runner.

The [calibration receipt](video-gva-hw-cpu-validation.json) records source and
executable hashes and both control results. The local debugger reports the two
target locations as `hardware`; the byte comparison is additional evidence,
not a hardware execution proof for the GTX.

```bash
python3 bridge/experiments/video_gva_hw_witness/cpu_calibration.py \
  --out '/path/to/nvidia-880m-lab/bridge/results/lldb-hw-calibration-new'
```

The result directory must not already exist. The script builds and signs only
its own two test binaries, uses `lldb --no-lldbinit`, and records full output
in that directory. Its wrong-base control must fail to arm and still exit zero.
