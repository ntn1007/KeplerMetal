# Typed render-pipeline selection: bounded laboratory experiment

An original Metal shader uses `render_command.set_render_pipeline_state` and
then draws a triangle. Its AIR is translated to an explicit project-owned
context and submitted through the installed NVIDIA compiler and driver. The
translation preserves entry-point dataflow and command order. A 16-byte root
contains a context pointer and an opaque, process-local pipeline token; the
token is compared against a fixed transition table and is never dereferenced.
It is not an Apple `MTLResourceID` or native Apple ICB identity.

The existing render-state catalogue and materializer receive the resulting
record. A laboratory client manually constructs its context, owns the tokens,
retains its resources and submits a producer dispatch before rendering. The
two eligible pipeline states use the same vertex and fragment bindings and
geometry, but differ in interpolation: smooth versus flat. This is an explicit
adapted application, not a transparent implementation of the Metal API.

The valid token changes the state identifier; a foreign token produces an
inactive identity. With no producer dispatch the initial state is retained.
The helper checks a bounded inline table, slot, identity, token, version and
reserved fields. These checks do not sandbox arbitrary GPU pointers; this
experiment uses only allocations constructed and retained by its test host.
The new C++ transition planner is not connected to this host or the runtime.
The host's manually constructed table does not implement general pipeline
ownership, arbitrary state creation, lifetime enforcement or application-facing
argument encoding. It must not be used as a production integration.

The compute probe independently checks complete record and witness bytes,
guards, wrong token/source/slot, nonzero reserved data, invalid extension and
header, and no dispatch. Before any dispatch, a separate signed construction
host captures the native NVIDIA program. Its exact library, driver and code
fingerprints are checked again at execution, and offline disassembly rejects
unresolved native calls. This proves only the tested, pinned program and cases.

The rendering probe checks all 12,288 floating-point channels against an
independent CPU oracle, with guarded record/root/context readbacks. Smooth
interpolation is checked per pixel; the flat reference must be a constant input
vertex colour, and full images are compared against a separate native direct
draw. The foreign-token and missing-dispatch controls must produce different
images from the switched result. No performance comparison is made.

On October 27, 2026, two cohorts completed in 36 signed, nonoverlapping hosts:
20 rendering hosts checked 245,760 float channels with maximum CPU error
5.97e-8, and 16 compute hosts included 14 dispatches. All ten native image
pairs and ten repeated image pairs matched byte for byte. The active image
differs from the no-dispatch image in 9,216 channels and from the foreign-token
image in 6,144 channels. These are bounded correctness observations, not a
general pipeline implementation. [Audit and fingerprints](typed-pipeline-render-validation.json).
An independent export of the source rebuilt the producer library and the two
test executables byte-identically to those used in the cohort. Its seven-object
runtime build and 351 CPU tests passed; no second GPU cohort was required to
establish identity of those executable files.

## Reproduction

Use the matching macOS/SDK/driver profile, a fresh output path, a separately
built seven-object runtime and an existing `envydis`. Never overlap GPU hosts;
all inspection and execution runs use the same common reservation root.

```sh
python3 tools/build_from_source.py --out build/pipeline-runtime
python3 bridge/tools/public_air_pipeline_binding.py build --out /absolute/producer
python3 bridge/tools/public_air_pipeline_binding.py inspect --build /absolute/producer \
  --out /absolute/inspection --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_pipeline_binding.py certify --run /absolute/inspection \
  --envydis /absolute/envytools/envydis
python3 bridge/tools/public_pipeline_binding_compute.py build \
  --inspection /absolute/inspection --out /absolute/compute-build
python3 bridge/tools/public_pipeline_binding_render.py build \
  --library "$PWD/build/pipeline-runtime" --producer /absolute/producer \
  --inspection /absolute/inspection --out /absolute/render-build
```

The compute modes are `active`, `wrong_token`, `foreign_source`, `wrong_slot`,
`row_reserved`, `bad_extension`, `bad_header`, and `no_dispatch`. The render
modes are `gpu`, `native`, `no_dispatch`, `no_dispatch_native`, `foreign`,
`foreign_native`, `reverse`, `reverse_native`, `reverse_no_dispatch`, and
`reverse_no_dispatch_native`. For two serial cohorts, use fresh paths
`/absolute/cohort/pipeline-compute-MODE-01` through `-02` and similarly
`pipeline-render-MODE-01` through `-02`:

```sh
python3 bridge/tools/public_pipeline_binding_compute.py run \
  --build /absolute/compute-build --out /absolute/cohort/pipeline-compute-active-01 \
  --certificate /absolute/inspection/certificate.json --mode active \
  --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_pipeline_binding_render.py run \
  --build /absolute/render-build --out /absolute/cohort/pipeline-render-gpu-01 \
  --mode gpu --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/audit_pipeline_binding_cohorts.py /absolute/cohort \
  --out /absolute/pipeline-audit.json
python3 -m unittest discover -s tests -v
python3 tools/check_publication.py
```

The next integration must derive tokens and rows from retained, certified
pipeline objects; validate roots and aliases; enforce lifetimes through
completion; and expose a scoped argument encoder with conservative rejection.
Then it needs application-level and regression qualification. Features beyond
this draw/selection profile, general Metal support and system-driver changes
remain open.
