# State changes after an incomplete triangle

Two isolated GTX processes exercised the execution-time guard added with the
[bounded incomplete-triangle extension](PARTIAL_TRIANGLE_ICB.md). Each used the
same qualified runtime archive and registered both the pinned legacy pipeline
and a distinct native stage-in pipeline.

After a two-vertex legacy triangle was encoded, the client changed its pipeline
to the stage-in pipeline, or added a vertex-buffer binding. It also changed the
pipeline after encoding a two-index triangle. In all three cases, execution
raised the expected `KeplerCPUICBUnsupported` error **before submission**. The
client ended and discarded each uncommitted command buffer. Thus six refusals
were observed across the two processes.

The same processes also tested unchanged incomplete state, restoration of the
legacy pipeline after a change, and a copied incomplete command whose original
was then changed. Each completed a render pass producing the expected empty
image. A complete three-vertex control produced the expected full-color image.
The independent [audit](partial-triangle-state-guard-validation.json) checked
**98,304 float channels and 4,096 guard bytes** across eight completed command
buffers. The incomplete commands were skipped by the adapter; their results do
not demonstrate execution of vertex instructions. The complete draws and
readbacks provide a GPU execution control.

The tests cover one registered stage-in pipeline, one vertex-buffer binding,
a 16-bit indexed case and the documented copy operation. They do not qualify
unrelated shaders, fragment-binding changes, concurrent state mutations, every
copy/lifetime scenario, unmodified applications or general Metal ICB behavior.
The reservation coordinates participating lab tests only. No system driver,
OCLP or firmware was modified, and no performance claim is made.

## Reproduction

The recorded client links the existing runtime archive and requires the pinned
private legacy and vertex metallibs and vertex manifest. Run from the source
repository with new output paths; never retry while a process or reservation has
an unresolved outcome.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/partial_triangle_state_guard
A="$PWD/build/partial-triangle-new"
python3 tools/build_from_source.py --out "$A"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" \
 --legacy '/path/to/render_state_carrier.metallib' \
 --vertex "$R/cpu-icb-vertex-prepared-04/vertex_io_carrier.metallib" \
 --manifest "$R/cpu-icb-vertex-prepared-04/cpu_icb_vertex_profiles.json" \
 --out "$R/partial-state-build-new"
python3 "$E/experiment.py" run --lab "$LAB" --build "$R/partial-state-build-new" --out "$R/partial-state-1-new"
python3 "$E/experiment.py" run --lab "$LAB" --build "$R/partial-state-build-new" --out "$R/partial-state-2-new"
python3 "$E/audit.py" --build "$R/partial-state-build-new" --archive "$A" \
 --runs "$R/partial-state-1-new" "$R/partial-state-2-new" --out "$R/partial-state-audit-new.json"
```

The test assets remain private; their hashes and archive identity are verified
before building. A changed device, driver, compiler output or runtime requires
separate qualification.
