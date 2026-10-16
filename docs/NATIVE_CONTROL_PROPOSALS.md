# Native control reservation proposals

Two additional NVIDIA-generated programs pass 24 GPU trials with manually selected reservations from a new offline analyzer. The analyzer never changes a pipeline or authorizes execution. The common allocation API remains fixed at 4,096 bytes. This advances branch A, native allocation correctness; it adds no Metal API or installed-driver change. [Scoped evidence and hashes](native-control-proposal-validation.json).

## Analysis and its limits

`bridge/tools/propose_native_control_reserve.py` binds every listing word to the original SM30 bytes and SHA-256. It checks control opcodes, predicates, signed relative targets, scheduling markers, complete listing coverage, metadata size/register/allocation consistency, structured forward regions and bounded abstract state exploration. Unsupported execution opcodes/modifiers, inconsistent targets, crossing regions, stack underflow and exploration limits cause refusal.

The abstract state is a program counter plus forward SSY/JOIN targets. Predicates are independent choices. Warp masks, predicate dataflow and divergent BRA tokens are omitted. A finite result is **not a hardware SIMT depth or upper-bound certificate**. Valid native code can target scheduling words and place a terminal self-branch on a 64-byte boundary. An earlier analyzer wrongly imposed NAK's layout conventions; its source and refusals remain archived locally. The current audit checks 36 recorded targets to scheduling words and three boundary tail branches against actual bytes. Portable tests preserve both counterexamples.

The proposal is `max(native_word11, max(0, MesaCRS(abstract_depth) - 512))`, with an upward-only policy ceiling of 4,096. MesaCRS returns zero through depth 16, 1,024 through 32, then `align512((depth + 32) * 16)`. The subtraction uses the previously observed macOS prepared CRS relation, `align512(word11) + 512`. Applying Mesa's sizing to this abstraction remains a cross-compiler hypothesis.

All 29 archived profiles are accepted by this restricted analyzer. This is not qualification of all 29 proposed settings. It proposes an increase for a depth64 program that already works with the native setting. It is neither a minimum-reservation algorithm nor an automatic allocator.

## New GPU qualification

The two cases use unchanged native code, original libraries and the existing standalone `NativeControlReserveExperiment.mm` factory. Only constructor allocation words 9/11 increase. Whole-payload and code identity are checked after the native constructor returns. This is constructor-payload evidence, not independent readback of resident instructions. These cohorts do not capture or replay QMDs.

| Exact source variant | Abstract depth | Native word11 | Tested word11 | Prepared CRS relation | New trials | Exact uint32 results |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nested96 with entry witness | 193 | 2,080 | 3,584 | 4,096 | 12 | 17,936 |
| Nested96 with reloaded immutable bounds | 191 | 2,048 | 3,072 | 3,584 | 12 | 17,936 |

Each cohort covers group sizes 1, 31, 32, 33, 64, 128, 256, 512, 1024 and selected multigroup launches, up to 2,048 invocations per dispatch. Total: **24 compute command buffers, 35,872 exact uint32 values, 8,968 final invocation witnesses and 12,288 intact input/output guard bytes**, with zero incorrect results. The common laboratory lease and terminal manifests establish serialized processes. CPU expected answers were not uploaded to the GPU.

Forty-eight new input/output files match their archived 4,096-byte counterparts. Original native failures remain verified: the entry variant writes entry markers without final answers; the reload variant leaves output canaries unchanged. These failures were re-audited without GPU replay. The original nested96 setting of 3,584 had already been tested and is reused, excluded from new counts. The old threshold auditor also passes; its historical counts are not new executions.

An initial launch preflight ran before compilation completed and stopped on missing inputs before GPU execution; its failure is retained. The sweep verifier requires explicit `--variant reload_bounds`; its default nested selection refuses those assets. Existing nested proof dictionaries remain unchanged so historical equality checks still work.

## Reproduction

The supported source-only build and dependency recovery remain in [BUILDING.md](BUILDING.md) and [DEPENDENCIES.md](DEPENDENCIES.md). No proprietary shader, command capture or driver is distributed. These commands assume the original named fixtures beneath `bridge/results/`; first regenerate and qualify them using the native source/observer workflow in [NATIVE_ALLOCATION_THRESHOLDS.md](NATIVE_ALLOCATION_THRESHOLDS.md). Preserve mismatches when another SDK/driver generates different bytes.

From `bridge/`, use new output directories and serialize GPU cohorts:

```sh
python3 tools/propose_native_control_reserve.py \
  --observations results/control-flow-entry-observations-20261015 \
                 results/control-reduction-reload-observations-20261015 \
  --out results/proposal-review.json

python3 tools/build_native_reserve_sweep.py \
  --native-build results/control-flow-entry-build-20261015 \
  --observations results/control-flow-entry-observations-20261015 \
  --reserve 3584 --out results/entry3584-build
python3 tools/run_command_ir_runtime.py \
  --build results/entry3584-build --out results/entry3584 --mode depth96
python3 tools/verify_native_reserve_sweep.py \
  --root results/entry3584 --build results/entry3584-build \
  --native results/control-flow-entry-build-20261015 \
  --observations results/control-flow-entry-observations-20261015 \
  --reserve 3584 --depth 96 --out results/entry3584-proof.json

python3 tools/build_native_reserve_sweep.py \
  --native-build results/control-reduction-reload-build-20261015 \
  --observations results/control-reduction-reload-observations-20261015 \
  --reserve 3072 --out results/reload3072-build
python3 tools/run_command_ir_runtime.py \
  --build results/reload3072-build --out results/reload3072 --mode depth96
python3 tools/verify_native_reserve_sweep.py \
  --root results/reload3072 --build results/reload3072-build \
  --native results/control-reduction-reload-build-20261015 \
  --observations results/control-reduction-reload-observations-20261015 \
  --reserve 3072 --depth 96 --variant reload_bounds \
  --out results/reload3072-proof.json
```

These launchers use their checkout's bridge reservation root. To audit an existing lab from the public checkout, use the explicit root below. Do not launch independent checkout cohorts against the same GPU.

```sh
python3 bridge/tools/audit_native_control_proposals.py \
  --lab-root "$LAB_BRIDGE" --out "$LAB_BRIDGE/results/new-proposal-audit.json"
python3 -m unittest discover -s tests -v
```

The aggregate auditor is CPU-only and needs the historical fixtures named in its source. Its exact source is shared between the lab and public export. Portable tests need none of those binaries. The runtime/archive, 36 runtime sources, 83 system hashes and OCLP remain unchanged. New M1 execution, GPU qualification of the separately rebuilt public archive, benchmarks and physical-VRAM measurements were NOT RUN for this milestone.

## Sources and remaining work

- Mesa 26.2.4, recorded upstream commit `96cb43121031992b85767f9c1be8f3f48e22b1d2`: [`sm20.rs`](https://gitlab.freedesktop.org/mesa/mesa/-/blob/96cb43121031992b85767f9c1be8f3f48e22b1d2/src/nouveau/compiler/nak/sm20.rs), `crs_size`, `OpBra`, `OpSSy`, `OpSync`. Other project patches exist locally; the sizing function was checked identical to the original archive.
- envytools commit `f102b82381f3f11cee113d16374c87091db039d9`: [disassembler sources](https://github.com/envytools/envytools/tree/f102b82381f3f11cee113d16374c87091db039d9/envydis); pinned SM30 listings checked word-for-word. Tesla documentation is not treated as proof of Kepler stack capacity.
- NVIDIA [CUDA 9.1 binary utilities](https://docs.nvidia.com/cuda/archive/9.1/cuda-binary-utilities/index.html): Kepler control-instruction inventory, not a complete stack model.
- [Earlier CRS/QMD observations](NATIVE_ALLOCATION_QMD.md) and [segmented-control discrimination](NATIVE_SEGMENTED_CONTROL.md).

A sound model or explicitly bounded per-program qualification contract is still required before runtime use. Arbitrary shader ABI/compilation, complete Metal functionality, video, full VRAM pressure, display/power and transparent application integration remain separate requirements of the full project. No general performance gain follows from this milestone.
