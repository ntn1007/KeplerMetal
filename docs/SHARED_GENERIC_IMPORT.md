# Shared compute and graphics import transport

The historical `KPCreatePipeline`, fragment, vertex, combined graphics,
tessellation and staging-buffer C functions now forward to the MRC transport
already used by the certified native CAS and approved FP64 paths. The retained
return ABI is unchanged. There is one constructor mutex and one thread-local
import context instead of two independent callback replacements.

Nested imports are refused before taking that mutex or changing wrapper
thread-local state. Graphics now checks the same actual PCI `10de:1198` ancestry
as compute and requires observed constructor restoration before accepting a
pipeline. The certified-CAS entry refuses nesting before certificate parsing or
exception cleanup; an invalid nested certificate is a separate refusal control. Unknown driver hashes still fail. Both exact qualified whole-file
hashes are described in [DRIVER_PROFILES.md](DRIVER_PROFILES.md).

The installed driver still owns allocation, submission and the display. There
is no system modification, new Metal-family declaration, Linux driver port,
general compiler fix or performance claim. Tessellation and indirect drawing
were existing native capabilities; this work consolidates their experimental
program-import path on the current profile.

## Qualification

The public seven-object archive has SHA-256
`70818a656f9cb518d77da924cb48f0225ba78a5a2c5fc1b24370675aaa8e58c4`.
The source baseline is macOS 26.7.1 / 25G241, SDK 26.2, Apple clang 17,
baseline x86_64. The installed Metal driver is the exact `e240d54a…` profile.
All GPU clients are freshly linked to this archive; no old host or runtime
object is reused. [Machine-readable qualification](shared-import-validation.json).

The final reception has 39 signed terminal nonoverlapping processes: 22 vertex/
fragment trials and 16 tessellation trials complete 38 render command buffers;
one host checks import contracts without dispatch. The independent auditor
checks 270,336 raster float channels (including the blank indirect control),
13,144 tessellation invocations / 52,576 value channels, 6,144 guard bytes and
16,356,608 untouched tail bytes. Eight native/import coordinate-multiset pairs
match. Nine direct native/import image comparisons differ as expected, while
each matches its own CPU oracle. Forty-six constructor imports are verified;
four nested attempts and one cached no-callback pipeline are refused. Thirteen
indirect argument words, including the four zero-control words, match their
CPU expectations. There is no throughput measurement.

The reception cohort separates:

- Native versus imported post-tessellation evaluation at factors
  0/1/2/4/8/16/32/64, with private output buffers, captured coordinates, squared
  values, untouched tails and byte guards. The imported program produces a
  distinct affine transformation. A portable CPU oracle checks both programs;
  coordinate multisets match between each native/import pair, independent of
  atomic output order. Factor zero must produce no invocations.
- Smooth/perspective, linear and flat interpolation in native, vertex-only,
  fragment-only and combined import modes. A separate Python raster oracle
  computes every float channel from the source vertices and draw parameters.
- Vertex-start, 16/32-bit indexed draws, positive/negative base vertex,
  instancing, base instance, and GPU-produced private indirect arguments.
  The native empty-argument producer must leave the image blank. These are
  native indirect draws, not GPU-generated Apple ICBs.
- A constructor-only host: a proxy deliberately attempts four nested imports,
  then three host threads concurrently call generic compute, combined graphics
  and certified CAS factories. The cached compute request must be refused with
  zero constructor imports; the uncached outer compute and graphics/CAS imports
  must succeed and restore the constructor. No user GPU work is dispatched by
  this host. Host concurrency is not evidence of overlapping GPU execution.

Preliminary failures are preserved separately. One capture-client build had a
duplicate local variable name. The first concurrency test expected success
from an already cached pipeline; the actual safe refusal is now checked
explicitly, including its exact zero-import condition. A historical 192-byte
vertex fixture lacked the already-known `baseInstance` adjustment and produced
3,072 incorrect blue channels. The final cohort uses the existing qualified
256-byte fixture (`97fad573…`), matching the published compiler source. This is
fixture correction, not a newly discovered or repaired system-driver defect.
The initial publication test failure reflected the not-yet-updated source
manifest; it is retained with the preliminary logs.

## Regression on the same final archive

A further 23 signed terminal hosts repeat the five-client prepare/FP64/
conversion/CAS/render suite from [ADAPTER_PROFILES.md](ADAPTER_PROFILES.md),
then native/imported 8/16 KiB local-memory baselines, missing-dispatch controls
and constructor/refusal cases from [LARGE_LOCAL_MEMORY.md](LARGE_LOCAL_MEMORY.md).
All 62 final hosts are terminal and nonoverlapping. The same explicit common
reservation is used throughout.

- FP64/conversions: 1,269 user dispatches and 6,095,853 checked results, with
  the existing finite-bit/quiet-NaN contract. Missing-producer controls retain
  259,092 expected differences from the complete chain.
- CPU ICB CAS: 29,440 repaired operations / 117,760 exact uint32 values. The
  native baseline retains 25,066 expected defective old-return words; its
  success/final/index checks are evaluated separately.
- Existing render adapter: 11 command buffers / 135,168 exact float channels.
- Local memory: 12 compute dispatches / 5,632 exact uint32 results, 9,216 guard
  bytes and 2,816 expected words absent without dispatch. Constructor and
  refusal hosts submit no user GPU command buffers. This is a baseline, not a
  repeat of the full earlier local-memory launch matrix.

The raw regression oracles are rerun offline after execution. One hundred
portable CPU tests pass. All 87 system references match their before-work
hashes; OCLP and the installed driver are unchanged. Earlier intermediate
archives and failed or superseded fixture cohorts are excluded from these
final counts. The final archive includes the additional early malformed-CAS
nesting refusal; an earlier completed normal-path cohort is retained only as
preliminary evidence.

## Reproduction

Use the local compiler/asset prerequisites from [BUILDING.md](BUILDING.md) and
[DEPENDENCIES.md](DEPENDENCIES.md). Generate the vertex fixtures using the
published `vertex_io_compile.c`, including its `CB1[0x6c4]` base-instance
adjustment; the early reproduction fixture predates that correction. Generate
the tessellation capture and CAS certificate assets using their existing
source workflows. These compiled assets are not distributed. The C and MSL fixture sources match their archived qualified versions. The
resource ABI header has only two additional enum constants unused by these
fixture compilers; program assets are reused by exact hash, not regenerated in
this phase. The reception
builder checks every selected fixture against
`bridge/tools/generic_import_fixture_pins.json` before copying it; changing a
pin is not a substitute for qualification. No clean-checkout bootstrap of all
historical compiler dependencies is claimed.

Set `KP_VERTEX_ASSETS`, `KP_TESS_ASSETS`, `KP_CAS_ASSETS` to those local fixture
directories, `KP_WORK` to a new workspace output directory, and `KP_LAB` to
the existing common reservation root for this physical GTX. Run serially:

```sh
set -e
python3 -B tools/build_from_source.py --out build/shared-local
mkdir "$KP_WORK"
python3 -B bridge/tools/public_generic_import.py build \
  --library build/shared-local --vertex-assets "$KP_VERTEX_ASSETS" \
  --tess-assets "$KP_TESS_ASSETS" --cas-assets "$KP_CAS_ASSETS" \
  --out "$KP_WORK/clients"
mkdir "$KP_WORK/cohort"
kp_run() {
  label="$1"
  shift
  python3 -B bridge/tools/public_generic_import.py run \
    --build "$KP_WORK/clients" --out "$KP_WORK/cohort/$label" \
    --reservation-root "$KP_LAB" "$@"
}
kp_run contract --kind contract --mode contract
for factor in 0 1 2 4 8 16 32 64; do
  for mode in native imported; do
    kp_run "tess-$mode-$factor" --kind tess --mode "$mode" --factor "$factor"
  done
done
for interpolation in smooth linear flat; do
  for mode in native vertex fragment both; do
    kp_run "vertex-$interpolation-direct-$mode" --kind vertex --mode "$mode" \
      --interpolation "$interpolation" --draw direct --memory private
  done
done
for draw in vertex-start indexed16 indexed32 base-vertex negative-base-vertex \
            instanced base-instance indirect indirect-indexed indirect-control; do
  kp_run "vertex-smooth-$draw-both" --kind vertex --mode both \
    --interpolation smooth --draw "$draw" --memory private
done
python3 -B bridge/tools/audit_generic_import.py "$KP_WORK/cohort" \
  --out "$KP_WORK/cohort-audit.json"
```

Each run freezes sources, oracles, inputs and executable; signs a fresh copy;
inherits the common reservation; records terminal process state; and checks raw
results. A failure stops the cohort. Inspect that exact process and reservation
before another launch; never overwrite a failed output directory. The portable
auditor rechecks all 39 selected hosts and native/import controls without
executing Metal. This is cooperative laboratory reservation, not exclusive
ownership against WindowServer.

## Compatibility and remaining limits

Link the complete `libKeplerMetal.a` from `tools/build_from_source.py`.
`KeplerProgramImport.mm` is now a facade with internal CAS dependencies; compiling
it alone as an old standalone dylib is no longer a supported build. Historical
frozen binaries remain preserved; historical standalone builders require their
original source snapshot. Both import translation units still use MRC; other
core objects retain their existing ARC settings.

The generic API still requires a truthful matched shader/resource ABI and
approved code. It is not a validator for arbitrary machine code. Cached paths
with no constructor callback remain refused. Tessellation topology, every
possible shader, all resource lifetimes and full Metal conformance are not
qualified by this cohort. API resource counters are not physical VRAM measures.
No throughput benchmark or CPU relief claim is made. Transparent integration
for ordinary applications, the remaining Metal feature gaps, native hardware
video and general driver modernization remain open work.
