# AIR render-command reset changes a verified rendered image

The qualified typed AIR producer now resets a real render-state record before
the existing catalogue materializer consumes it. The resulting image matches
an independent CPU raster oracle and a direct-draw reference that omits the
targeted draw. This connects the [preserved shader dataflow](AIR_RESET_DATAFLOW.md)
to the [existing render path](GPU_RENDER_STATE_CATALOGUE.md).

The original SDK-typed shader is unchanged. Its translated program still uses
the NVIDIA native compiler and the explicit KeplerMetal context. This remains
adapted-application integration, not Apple's native ICB resource ABI or a
replacement installed driver.

## Ordering and lifetime

Each retained command buffer uploads ordinary inputs, generates four render
records on GPU, then runs the certified reset producer. The context points to
the live records buffer, with capacity four. Count four, seed three and mask
zero produce indices 3/11/7/15; only index three is in range. Materialization
and drawing follow in the same command buffer. The candidate never reads GPU
state choices or records on CPU to decide what to encode.

`AIRCertifiedResetPipeline.mm` is a separate MRC unit. Its C-linkage factory
returns a retained native PSO with `NS_RETURNS_RETAINED` for the ARC host. It
checks driver/library/native-code certificates and restores the temporary
constructor observer **before** installing the render scope. This avoids ARC
changes to the original native constructor's ownership behavior.

The host retains reset inputs and its PSO through completion. Existing scope
and ICB objects are released after an inner autorelease-pool drain, before
commit; native resources remain valid. The tested records, context, root,
indices and witness buffers all report `Private` storage. Readback uses Metal
blits after rendering, rather than CPU writes that simulate shader effects.

## Reception and controls

Twenty-one final signed, terminal, nonoverlapping processes cover three repeats
of seven modes:

- `air_gpu`: translated producer, GPU record materialization and drawing.
- `air_native`: the same producer plus a direct-draw image reference that
  omits slot three. CPU state resolution is confined to this reference.
- `air_reference`: an independently written native MSL reset producer feeding
  the same record materializer.
- `air_no_reset` / `air_no_reset_native`: omit the reset dispatch.
- `air_bad_context` / `air_bad_context_native`: run the same translated program
  with one invalid context-magic bit. Records remain intact, while shader
  arithmetic still produces the expected witness.

The final reception checks **168 images / 2,064,384 float channels**, with zero
numerical error, plus **120 reset dispatches and 480 exact uint32 witnesses**.
It checks 119,808 existing raster/materializer guard bytes and 86,016 additional
reset guard bytes. All 120 reference/control image pairs, 112 repeat image
pairs and 3,328 repeat readback pairs match. Dynamic pointer-bearing root/context
files are checked independently against owned addresses rather than compared
across processes.

Reset changes trials 0/1/3/4/6 in each repeat: **19,992 float channels** differ
from the missing-reset control. Trials 2/5 already reject the targeted draw;
trial 7 omits the ordinary producer. All three remain unchanged, as expected.
The valid/invalid-context pair preserves other render inputs and numerical
witnesses; its normalized context differs by exactly the intended magic bit.
One separate successful eight-frame pilot is excluded from these totals.

All **277 CPU tests** pass, including eleven new contract/oracle tests. The
default host rebuilt without the opt-in macro is byte-identical to its previous
GPU-qualified executable and preserves all assets; the current default verifier
also rechecks the twelve prior cases / 1,093,632 channels. This is archived-data
reanalysis, not twelve new GPU runs.

A complete fresh seven-object source build reproduces every object and archive
member payload. Its archive header metadata differs, but linking it produces
the exact GPU-tested application and all ten assets again. No core runtime
source changes are needed. The first CPU build exposed C++ linkage differences
between ARC and MRC output-pointer qualifiers; explicit C linkage fixes that
before any GPU launch. The failed CPU build remains archived.

Environment: macOS 26.7.1/build 25G241, SDK 26.2, Apple Metal 32023.864,
clang 17.0.0, GTX 880M/GK104 PCI `10de:1198`. All 87 inventoried system files
remain unchanged. Exact hashes and counts:
[validation](air-reset-render-validation.json),
[source chain](air-reset-render-source-chain.json).

## Reproduce from public source

First reconstruct and qualify the producer and its two inspection certificates
using [AIR_RESET_DATAFLOW.md](AIR_RESET_DATAFLOW.md). Build a complete runtime
from this checkout and use fresh output directories:

```sh
python3 tools/build_from_source.py --out build/fresh-runtime
python3 bridge/tools/public_render_state_catalogue.py build \
  --library build/fresh-runtime --out /absolute/fresh-render-build \
  --air-reset-build /absolute/qualified-producer-build \
  --air-reset-inspections /absolute/producer-session
python3 bridge/tools/public_render_state_catalogue.py run \
  --build /absolute/fresh-render-build --out /absolute/render-session/cohort/0/air_gpu \
  --mode air_gpu --reservation-root /absolute/common-lab/bridge
```

Create parent directories first. Run all seven modes sequentially under
`cohort/{0,1,2}/{mode}`; stop on any failed or unresolved signed host. Then:

```sh
python3 bridge/tools/audit_air_reset_render.py /absolute/render-session \
  --build /absolute/fresh-render-build --out /absolute/fresh-audit.json
python3 -m unittest discover -s tests -v
python3 tools/check_publication.py
```

The opt-in macro is only a test-host build option. No SDK, system framework,
driver, OCLP or global application configuration is replaced. No speed benchmark,
M1 reception, transparent ordinary-application integration or general Metal
3/4 support is claimed. Public factory/root-encoder integration and additional
command operations remain open.
