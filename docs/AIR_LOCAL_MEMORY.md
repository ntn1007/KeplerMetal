# MSL/AIR private arrays and register spills

This extends the alternative compiler path. The installed native Metal driver already supported private arrays and register spills. No system component, device family, native carrier profile or runtime implementation changed for this milestone.

The exact same original `bridge/src/kepler_local_memory.metal` is compiled twice: through the native Metal/NVIDIA pipeline and through MSL → AIR → OpenNVDA NIR → NAK SM30. The latter uses the opt-in allocation-preserving import described in [LOCAL_MEMORY.md](LOCAL_MEMORY.md). It no longer needs manually written NIR for these programs.

## Qualified behavior

The new cohort passed 180 compute trials and 48 missing-dispatch controls: 84 native, 96 AIR/NAK positive trials, and 48 controls. The importer includes an eighth compiler program with deliberately forced spilling. Group sizes are 1,31,32,33,64,128,256,512,1024 plus selected multiple-group launches. These are full groups, including partial warps; nonuniform groups were not tested.

The independent CPU oracle recomputed 269,040 exact uint32 outputs, 67,260 per-invocation witnesses and 116,736 guard bytes, with full input-buffer comparisons. Seven matched native/AIR programs produced 168 identical input/output files across their twelve trials. Array contents are exercised through checksums and state; individual internal scratch bytes are not directly read back. The fixture's local-array seed contribution cancels in its initial state; do not count that as independent local-array seed coverage.

| Program | AIR/NAK scratch bytes | Spill/fill pairs | Actual GPRs |
| --- | ---: | ---: | ---: |
| local_control | 0 | 0 | 24 |
| local32 | 128 | 0 | 24 |
| local256 | 1024 | 0 | 24 |
| local1024 | 4096 | 0 | 24 |
| pressure32 | 0 | 0 | 40 |
| pressure64 | 28 | 7 | 63 |
| pressure96 | 156 | 39 | 63 |
| pressure32 forced | 80 | 20 | 18 |

Forced spilling sets `NAK_DEBUG=spill` only in that compiler child; other children explicitly unset it. The imported allocation is at least 24 GPRs. Pressure programs use the qualified 224-byte native pressure carrier. Runtime archive identity remains `59f3a04d6c9929ec5c22034234e27006675174e076855df26a5b584f88f245ac`; this cohort does not requalify separately rebuilt runtime archives.

## Explicit resource contract

`KeplerLocalAIRLowering.inc` maps the frontend's packed push fields to the observed native ABI:

- Device uint input at buffer0 and device uint4 output at buffer1: native CB1 resource addresses.
- Constant buffer2: exactly four 32-bit fields, 16 bytes, statically located loads, mapped to CB2.
- One-dimensional full groups with zero origin; grid and local dimensions read from the native CB1 fields.

Entry types, address spaces, argument indices and buffer-location metadata are checked. A surviving/unhandled constant-buffer pointer is refused rather than mapped to an assumed GPU address. Textures, samplers, constant globals, shared allocations and external CRS are outside this harness. Dynamic constant offsets are currently refused even when a particular access could be safe. This is a bounded compiler/resource profile, not arbitrary MSL or arbitrary library support.

Eight offline contract cases passed: seven expected rejections and one valid translation after them. Rejections cover device/constant address-space mismatch, larger structs, swapped/moved bindings, dynamic constant offsets, missing entry and a wrong bank. They compile valid MSL first where applicable and never create a GPU pipeline. These controls do not certify the upstream parser for untrusted malformed AIR.

## Versions and identities

- Reference GTX880M GK104/SM30, 8GiB, on macOS26.7.1 build25G241; SDK26.2 / Apple clang17.
- OpenNVDA upstream reference `da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5`, with the existing local CAS-result fix and block-allocation ownership fix applied only to a frozen source fork.
- Mesa26.2.4 extracted tree. `96cb43121031992b85767f9c1be8f3f48e22b1d2` is an upstream reference, not a verified local checkout commit. The build manifest records all eleven effective linked archive hashes.
- Offline compiler SHA256: `271bfc1cfeb10596cc0bad2cb50c9a91ef1be66dfd5faa937d8763eb107054a5`.
- Programs manifest SHA256: `c740e1c18a7d7c92c9f01449960a3af7d80a5aed0f66fc757d2ebbe43e57e540`.
- Original MSL SHA256: `0b37e25fb4fdc33d8dfe728728cec750426f46143647ad6d1584ea6431be81d6`.

The initial offline compile failed because a new helper used an obsolete Mesa member. Replacing it with the current `nir_def_instr` API fixed compilation. A later delivery-verifier failure was a decoder-log filename mismatch. Both failures are retained in local provenance; neither involved a failed GPU execution. All current GPU sessions reached verified terminal state without a kill request.

## Reproduction and prerequisites

Obtain the external sources and developer tools according to [DEPENDENCIES.md](DEPENDENCIES.md). These commands use the established lab layout: existing qualified Mesa archives in `bridge/build/mesa`, the matching external frontend tree, the native carrier and the previously qualified runtime. No such binaries are redistributed. This is not a complete clean-checkout bootstrap; changing toolchain/carrier bytes requires a new profile qualification.

From `bridge/`, using new output directories:

```sh
python3 tools/build_air_local_programs.py --out results/air-local-programs-build-20261015-05
python3 tools/verify_air_local_contracts.py --compiler-build results/air-local-programs-build-20261015-05 --out results/air-local-CPU-contracts-20261015
python3 tools/build_local_memory_import_probe.py --out results/air-local-import-probe-build-20261015 --library results/local-memory-runtime-library-build-20261015-03 --native-build results/local-memory-native-probe-build-20261015 --programs results/air-local-programs-build-20261015-05 --extended
python3 tools/run_command_ir_runtime.py --build results/air-local-import-probe-build-20261015 --out results/air-local-control-20261015 --mode nak:local_control
python3 tools/verify_local_memory.py results/air-local-control-20261015
python3 tools/qualify_local_memory.py --build results/air-local-import-probe-build-20261015 --out results/air-local-qualification-20261015 --prefix air-local-extended-20261015 --control-reference results/air-local-control-20261015
python3 tools/verify_air_local_delivery.py --out results/air-local-memory-progress-20261015/final-verification.json
```

The last verifier intentionally audits this fixed lab layout and its system baseline; it is not a generic portable launcher. The `nak:` harness prefix now covers either direct-NIR or AIR-generated code; `source_language` in each program and frozen compiler/source hashes distinguish them. The current control is explicitly reused once by the matrix, not counted as another execution. All runners must share one designated reservation root across checkouts. The cooperative lease does not exclude WindowServer or arbitrary GPU applications.

The summary [air-local-memory-validation.json](air-local-memory-validation.json) describes local evidence. Raw captures, GPU binaries, runtime archives and system files are not published; a summary is not independent hardware attestation. No new M1 reference, benchmark, speedup, installed-driver modernization or general Metal3/4 conformance is claimed. The full hardware objective remains incomplete.
