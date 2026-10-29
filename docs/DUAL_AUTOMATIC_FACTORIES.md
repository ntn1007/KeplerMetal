# Automatic compute and render ICBs in one scoped queue

One opted-in process can enable the existing queue-local automatic compute **and** render encoder factories on the same `KPCPUICBScope`, in either order. In the tested workload an indirect compute command writes indices into a private GPU buffer; a later indexed indirect render command in the same command buffer consumes them without an intermediate CPU read. The application uses ordinary command-buffer compute and render encoder factories after the explicit scope setup. This qualifies an existing path; it does not install a new driver or make the adaptation transparent to arbitrary applications.

## Evidence

Two manual-adaptation controls and four automatic processes (two per activation order) ran serially under the common cooperative GPU reservation. The independent mixed-domain oracle checked **54 frames, 663,552 float channels and 1,152 compute invocations** across the six processes. The nine output images for each process match the corresponding manual controls and repeats. The cohort includes disabled producer or consumer, zero-area geometry, resets, copied indirect commands and two refused cross-domain API operations. Each process restored its device and queue classes; all children reached terminal status. The auditor also compares the signed executable to the frozen build, replays the pixel/guard and native-packet oracle, checks source hashes, GPU identity and reservation intervals. [Sanitized audit](dual-automatic-factories-validation.json).

Each automatic process records 11 automatic compute-encoder and 11 render-encoder events. These counts include internal preparation encoders and are not a performance measurement. The test exercises a pinned shader, scene, resource layout and native driver profile, with explicit local opt-in. It does not establish concurrent queue restoration, arbitrary encoders, ordinary unmodified application compatibility, native Apple ICB identity or system-wide Metal support. The GPU reservation coordinates participating lab runners, not WindowServer or every GPU user.

The original mixed witness selected a boot-specific registry ID and its frozen verifier expected that same old number. A preliminary manual process exited with code 2 before scope installation or command submission because the current ID differed; it terminated normally and is excluded. The final witness resolves the Metal device to NVIDIA PCI `10de:1198` through public read-only IOKit and requires a unique match. For this experiment the verifier's single fixed-ID predicate is changed to check that recorded GPU identity and registry ID; all other mixed GPU checks are retained. The original verifier and adjusted verifier hashes are recorded separately in the audit. No driver, framework or OCLP modification is performed.

## Reproduce

Use the matching Kepler driver/SDK profile, locally retained pinned compute/render metallibs, and a common laboratory reservation root. Build outputs and all run directories must be fresh. `execute` is the manual-adaptation control; the other modes opt into both factories. Run sequentially, and inspect a process and reservation if its outcome is unknown before any retry.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/dual_automatic_factories
python3 tools/build_from_source.py --out build/dual-auto-new
A="$PWD/build/dual-auto-new"
B="$LAB/results/dual-auto-build-new"
python3 "$E/experiment.py" build --library "$A" \
  --compute /path/to/cpu_icb_gpu_indices.metallib \
  --render /path/to/render_state_carrier.metallib --out "$B"
runs=()
for n in 1 2; do
  for mode in execute auto-compute-first auto-render-first; do
    out="$LAB/results/dual-auto-$n-$mode-new"
    python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --out "$out" --mode "$mode" || exit 1
    runs+=("$out")
  done
done
python3 "$E/audit.py" --library "$A" --build "$B" --runs "${runs[@]}" \
  --out "$LAB/results/dual-auto-audit-new.json"
```

The original mixed verifier captures private command evidence only in the lab; proprietary GPU programs, command captures and Apple/NVIDIA binaries are not published.
