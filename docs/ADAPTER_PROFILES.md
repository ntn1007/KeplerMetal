# Current-profile FP64, indirect commands and rendering

The combined application adapters now use the same exact whole-file driver
policy as the qualified import path. `KeplerDriverProfile.h` admits only the
two files documented in [DRIVER_PROFILES.md](DRIVER_PROFILES.md); unknown hashes
still fail. FP64, CPU-encoded ICB scopes, native compute-command records and
native render records resolve their Metal device through PCI `10de:1198`,
instead of the old boot-specific registry entry ID. Packet, resource, shader,
library and reflection checks remain enforced.

This restores these experimental adapters on the current installed stack; it
does not install a driver or add a Metal-family flag. The FP64 program set and
CAS repair are the existing pinned programs, not newly generalized compilers.

## Fresh artifact qualification

On macOS 26.7.1 / 25G241, SDK 26.2, the seven-object source rebuild has SHA-256
`6ac7a6c15718aee68883bdcf9fc601af75496b8ee5e709c26c0a2af0f83aeefa`.
Five source clients were independently linked against this exact archive. The
final cohort has 15 terminal, nonoverlapping signed processes; a separate
four-process baseline regression covers local-memory imports on the same archive.

| Workload, including its missing-producer control | User compute dispatches | Numerical results checked |
| --- | ---: | ---: |
| FP64 add/multiply/FMA/divide/square root | 477 | 2,291,349 |
| Integer/float32 promotion and dependent addition | 153 | 734,961 |
| Reverse conversions and GPU roundtrips | 639 | 3,069,543 |
| **FP64/conversion total** | **1,269** | **6,095,853** |

Each positive and missing-producer case uses nine trials across group sizes
32/128/1,024 and counts 65/2,057/12,289. The 60 pinned programs cover 20 named
operations, including four rounding modes for float32/int64/uint64 outputs.
Finite results are compared bit for bit; NaNs follow the documented quiet-NaN
classification contract, not arbitrary-payload identity. This is not exhaustive
IEEE conformance. Input recipes contain inputs only. Execution stamps/indexes,
input/output guards, copied program ownership and constructor restoration are
verified. The three missing-producer controls have 259,092 differences from the
complete chain while matching their own CPU references. No CPU readback occurs
between the dependent GPU operations.

The CPU-encoded ICB client executes 23 records in six command buffers and checks
29,440 repaired CAS operations / 117,760 uint32 values. It covers registered
pipelines, bindings, copy/reset/range/empty cases, explicit refusal controls and
restoration before the final commit. A separate 23-record native baseline
preserves 25,066 incorrect return words in the original defective shaders while
checking their success/final/index behavior. These are expected defect controls,
not silently accepted correct results or a new general CAS fix.

The render client passes 11 render command buffers and 135,168 exact float32
channels. It exercises ordinary public ICB render selectors in the adapted
scope, inherited scissor, ranges/copy/reset, caller-pipeline state afterward,
Private index-buffer data dependence and seven API refusal cases. Forty-eight
raw files are checked. This is the existing bounded native render transport,
not full ICB support or a GPU-resident render-command implementation.

The separate local-memory baseline adds six compute dispatches, 2,816 exact
uint32 results, 6,144 guard bytes and 2,816 expected words absent without
dispatch. It covers the 8/16 KiB imported frames; the previous full launch
matrix was not repeated on this archive. All 87 system references match the
start-of-work observations. Ninety portable tests and the CPU-only linked
profile-policy acceptance/refusal checks pass.

Preliminary failures are retained separately: a duplicate summary field after
successful verification, missing generated reverse-input recipes, and an old
driver-hash refusal in the native command component. They are excluded from the
final counts. [Machine-readable adapter summary](adapter-profile-validation.json).

## Source build and reproduction

Start with a new complete source build, then point `KP_ASSET_SDK` to a locally
generated 60-program SDK with its original `FILE_MANIFEST.json`. The earlier
compiler/SDK asset workflows and their local prerequisites are described in
[BUILDING.md](BUILDING.md) and the combined SDK README. Those historical binary
fixtures are not distributed, and this is not a clean-checkout asset bootstrap.
The reception builder checks the asset manifest, copies selected source/header
files, generates the three raw input recipes and links all five clients. It
reuses no old host executable or runtime object.

```sh
python3 -B tools/build_from_source.py --out build/adapters-local
python3 -B bridge/tools/public_adapter_qualification.py build \
  --library build/adapters-local --asset-sdk "$KP_ASSET_SDK" \
  --out "$KP_WORK/clients"
python3 -B bridge/tools/public_adapter_qualification.py run \
  --build "$KP_WORK/clients" --out "$KP_WORK/fp64-prepare" \
  --reservation-root "$KP_LAB" --kind fp64 --mode prepare
python3 -B bridge/tools/public_adapter_qualification.py run \
  --build "$KP_WORK/clients" --out "$KP_WORK/fp64-execute" \
  --reservation-root "$KP_LAB" --kind fp64 --mode execute --trials 9
```

Use `forward` and `reverse` for the conversion clients. Their modes are
`prepare`, `execute`, `no_producer`; `--trials` is 1 or 9. The fixed ICB client
uses `--kind icb` with `register`, `prepare`, `execute` or `native`; the render
client uses `--kind render` with `prepare` or `execute`. Use new directories,
the same physical host reservation and serial launches. Failure stops the
cohort; inspect its exact process, lease and files before another launch.

## Remaining scope

This is application integration at levels 1/2. Ordinary unmodified applications,
general Metal 3/4 conformance, hardware video, power/display integration and
performance remain unfinished. FP64 calls use the adapted SDK; this does not
make `double` a generally supported type in the native MSL frontend. The
separate legacy generic import object still
has its original gate; it requires its own qualification and coordination with
the shared importer. Optional producer-thread-limit, GPU-generated command,
advanced rendering/texture and long-duration concurrency suites were not run
here. No benchmark or reduction in CPU load is claimed.
