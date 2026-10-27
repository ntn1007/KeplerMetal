# Eight-state render catalogue and quad preparation

The scoped, opt-in render catalogue accepts up to eight distinct certified
sources while preserving the existing maximum of sixteen flattened native
draw candidates. Two logical commands can therefore each have eight candidate
states. This is a software catalogue limit, not a claim about the GPU's maximum
or a Metal feature-set declaration. Larger combinations are refused before
materialization; normal applications do not use this adapter transparently.

The eight-state execution probe uses eight genuine, independently encoded
fragment argument buffers, each with a texture, sampler and nested parameter
buffer. A GPU producer selects each candidate in turn from the 64 bounded
transition rows. Its images are checked independently against CPU values and
ordinary native direct draws. A foreign pointer gives an empty image. Controls
refuse nine source objects, a 24-candidate catalogue, and a root alias.

A second probe uses two logical commands with eight candidates each. The CPU
seeds the selected state identities in a private record upload; the GPU
materializer writes the actual indirect draw arguments and sixteen witnesses.
The independent oracle checks every predicate, reason, argument and guard as
well as the final image. This probe establishes the 16-candidate materializer
path, not GPU generation of those two initial identities. Sixteen native draws
are encoded; the full-screen draws overlap, so witnesses are needed to validate
both logical commands. The materializer's shader is unchanged and retains its
existing exact library pin.

The CPU planner test builds the full cross-product of two pipelines, two vertex
buffers and two fragment buffers for each of two logical slots. For every start
and destination it checks all six setter orders, and rejects transitions whose
intermediate state is missing. This is a CPU model test, not execution of that
combined scenario on the GPU.

A new pinned typed AIR experiment contains the three setters and both indexed
draw widths. Its source compiles and the exact lowered program has been
constructed by the native NVIDIA backend and inspected for unresolved calls.
At this milestone there was no quad-context runtime or quad GPU dispatch.
Later integration and GPU qualification are described in [QUAD_RENDER.md](QUAD_RENDER.md).

The initial sixteen-candidate host did not compile because Objective-C did not
recognize `valueForKey:` on the typed Metal protocol; it was rebuilt with an
explicit object cast before any execution. The failed build is retained locally.

## Qualification and reproduction

The independent audit rechecks 19 eight-state GPU/reference/control hosts,
nine sixteen-candidate hosts and four same-runtime regression hosts. All 32
were serialized and terminal. It checks 344,064 output channels plus 344,064
input-texture channels, 144 sixteen-candidate witnesses, 13 native image pairs
and eight mutually distinct images. Maximum CPU error is zero in this cohort.
All 366 CPU tests pass both locally and from a clean source export. The export rebuilt both tested clients and the quad producer byte-identically and passed two additional GPU hosts. Those hosts and the construction-only inspection did not overlap the 32 audited hosts. [Hashes and audit summary](eight-state-validation.json).

Use the supported macOS/SDK/driver profile and a shared GPU reservation; run
one host at a time and use fresh output directories. Obtain `envydis` separately.
The GPU producer used for the eight-state probes is the already certified
fragment producer in [its reproduction instructions](FRAGMENT_BINDING_EXPERIMENT.md).

```sh
python3 tools/build_from_source.py --out build/eight-runtime
python3 bridge/tools/public_eight_state_fragment.py build \
  --library "$PWD/build/eight-runtime" --producer /absolute/fragment-producer \
  --inspection /absolute/fragment-inspection --out /absolute/eight-build
python3 bridge/tools/public_eight_state_fragment.py run --build /absolute/eight-build \
  --out /absolute/results/final-gpu7 --mode gpu7 \
  --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_sixteen_slot_fragment.py build \
  --library "$PWD/build/eight-runtime" --producer /absolute/fragment-producer \
  --inspection /absolute/fragment-inspection --out /absolute/sixteen-build
python3 bridge/tools/public_sixteen_slot_fragment.py run --build /absolute/sixteen-build \
  --out /absolute/results/sixteen-gpu7 --mode gpu7 \
  --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_quad_render.py build --out /absolute/quad-producer
python3 bridge/tools/public_air_quad_render.py inspect --build /absolute/quad-producer \
  --out /absolute/quad-inspection --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_quad_render.py certify --run /absolute/quad-inspection \
  --envydis /absolute/envytools/envydis
```

Run the mode sets and same-runtime regressions listed in
`bridge/tools/audit_eight_state_fragment.py`; then invoke that audit against the
results directory. Each run retains its own frozen oracle and reservation
receipt. No system driver, OCLP, firmware or WindowServer change is required.
