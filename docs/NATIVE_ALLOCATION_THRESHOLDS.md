# Native reservation thresholds and new programs

The unchanged common API now executes two additional NVIDIA-generated programs, with source nesting 104 and120, correctly on the GTX 880M. Both unmodified native baselines finish their command buffers with the output still at the canary value. Increasing only native allocation metadata corrects the results. The shader bytes, register count and native local/spill frame stay unchanged.

This is branch A behavior evidence and level 2 integration for adapted applications. It establishes more working programs; it does not establish a universal allocator or complete hardware/API coverage. [Machine-readable summary](native-allocation-threshold-validation.json) · [Common API](NATIVE_ALLOCATION_API.md).

## Adjacent measured settings

The same 12 launch configurations, seeds and inputs are used at each setting. Each correct cohort produces 17,936 exact uint32 values. The lower settings in this table leave all output words unchanged; inputs and guards remain intact. GPU code hashes match within each comparison.

| Source nesting | Original metadata word11 | Lower aligned setting: FAIL | Adjacent setting: PASS |
| --- | --- | --- | --- |
|65|1,584|2,048|2,560|
|96|2,080|2,560|3,072|
|104|2,208|3,072|3,584|
|120|2,464|3,584|4,096|

The 65/96 lower controls are previously recorded experiments, rechecked offline without GPU replay. The 104/120 programs and their adjacent-setting controls are new. These are thresholds between **tested** settings for the sampled programs and inputs, not universal minima or proof that all smaller settings fail. In particular, the source-level relation `align512(32 * depth)` matches these four upper settings; it has not been proven for arbitrary shaders.

The new native programs are 47,104 bytes/frame 1,892 bytes and 52,160 bytes/frame 2,208 bytes respectively, both at 63 GPRs. They stay within the already qualified code/frame bounds. Source nesting 120 does not mean that 120 dynamic hardware CRS entries have been independently measured.

## Static analysis and its limits

[`analyze_native_control_reserve.py`](../bridge/tools/analyze_native_control_reserve.py) binds 25 historical and two new listings to the actual code bytes, checking every decoded word and target. It computes forward `joinat` interval overlap and operation counts. These are lexical metrics, **not** dynamic CRS depth, a general upper bound or proof of execution.

Counting all `joinat` instructions is insufficient: the working sequential 96 program has 384 such instructions but only three forward intervals overlap, whereas the nested 96 program has 194 instructions and 193 overlapping intervals. Reachability, predicates, joins, loops and calls matter. The tentative comparison `align512(max(native_word11, 16 * lexical_overlap))` was selected for discrimination, not activated automatically in the runtime. It chooses 3,584 and 4,096for the two new programs, which pass. It is conservative relative to the measured 3,072 setting for the original96program; it is not a minimum rule.

The pinned [Mesa 26.2.4 SM20 source](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-26.2.4/src/nouveau/compiler/nak/sm20.rs) has a separate CRS calculation: zero through 16 entries, 1,024 through 32, then `align512((depth + 32) * 16)`. The local file contains other Kepler project patches, but this exact function is byte-identical to the original archive function, SHA256 `bd93939ea0f04cdc2c8fa483fcd659c4ad1b96bf6e319d84706119c8d091a539`. Mesa derives its depth from its own structured NIR stack, not from our NVIDIA listing metric. Its [QMD implementation](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-26.2.4/src/nouveau/compiler/nak/qmd.rs) rounds the CRS field to 512 bytes.

[envytools' pinned Fermi/GK104 ISA documentation](https://github.com/envytools/envytools/blob/f102b82381f3f11cee113d16374c87091db039d9/docs/hw/graph/fermi/cuda/isa.rst) explicitly leaves parts of control state incomplete. Its older shader-header description uses another stack-slot description. These sources are useful evidence, but do not by themselves prove the meaning of the macOS allocation field or a native compiler root cause. The next decisive task is mapping the decoded constructor allocation to the actual submitted native CRS/QMD fields.

## New GPU evidence

The new work contains 120 correct compute trials and 48 numerically defective controls, with 179,360 exact uint32 results,71,744 incorrect canary words and 86,016 intact guard bytes. The 48 failures remain actual numerical failures. A verifier returning `status: PASS` means this complete evidence, including the failures, matches its declared outcomes; it does not turn a defective native compiler result into successful computation.

Those failing104/120cases have no entry witness. Completed command buffers and encoded dispatch calls alone do not establish that their shader instructions started, where execution stopped, or that a hardware stack overflow occurred.

Each unchanged runtime archive receives 24 new lifetime trials for104/120: caller library/certificate bytes are overwritten and the factory autorelease pool is drained before dispatch. All results match the CPU oracle and the standalone corrected path. Four semantic comparisons cover 96 identical input/output files.

- Common six-object archive: `5636b0d0d158fc985bf9b1df5fd0e16b91909a9a6f48423c175272b7fe4ddb67`.
- Public seven-object archive: `9e26d4eb78b772585ae312e1e4ca1a72ef432f02935674ff7f67600cd4488a3c`.

These are new tests on unchanged archives, not inherited tests on a new build. The common API still requires reserve 4,096; smaller settings remain separate standalone experiments. The previous large matrix is unchanged. No new M1 run, benchmark, automatic allocator, installed driver change or measured VRAM saving is claimed. The 83 tracked system files and OCLP are unchanged.

## Reproduce from text

Use the pinned native driver/profile and an explicitly serialized lab reservation. Obtain the exact open source dependencies separately as described in [DEPENDENCIES.md](DEPENDENCIES.md). The source-only disassembler wrapper is now included:

```sh
cmake -S bridge/tools/envydis-build -B bridge/build/envydis-only \
  -DENVYTOOLS_SOURCE="$PWD/bridge/vendor/envytools-f102b82381f3f11cee113d16374c87091db039d9" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build bridge/build/envydis-only --target envydis -j2
```

The lab uses the included Bison 2.3 compatibility patch on the pinned envytools source; review/apply `bridge/src/envytools-bison23.patch` when using that parser version. This wrapper builds file parsers/disassembly only, with no GPU-access tools. It does not bundle envytools or any driver.

Generate and observe the new programs without copying an archived shader:

```sh
python3 bridge/tools/build_control_flow_probe.py \
  --out bridge/results/general-native-new --depths 104 120
python3 bridge/tools/observe_control_flow.py \
  --build bridge/results/general-native-new \
  --out bridge/results/general-observations-new
python3 bridge/tools/build_native_reserve_sweep.py \
  --native-build bridge/results/general-native-new \
  --observations bridge/results/general-observations-new \
  --reserve 3584 --out bridge/results/general-reserve-new
python3 bridge/tools/run_command_ir_runtime.py \
  --build bridge/results/general-reserve-new \
  --out bridge/results/general-result-new --mode depth104
python3 bridge/tools/verify_native_reserve_sweep.py \
  --root bridge/results/general-result-new --build bridge/results/general-reserve-new \
  --native bridge/results/general-native-new --observations bridge/results/general-observations-new \
  --reserve 3584 --depth 104 --out bridge/results/general-check-new.json
```

Use a separate build at 4,096 for 120. The observer creates native pipelines without dispatch. The numerical runner explicitly dispatches on the target GPU. Read both `observation_status` and `numerical_status`; verification of an observed failure is not a numerical pass. New directories are mandatory. No timeout-driven replay is permitted. Other checkouts must share the same host reservation root.

`verify_native_allocation_rule.py` audits the recorded milestone offline and requires its frozen private lab layout. The common/public API builds additionally require their locally reconstructed archives. The public source build is separate from GPU qualification; compiled Apple/NVIDIA artifacts and the raw binary results remain excluded from GitHub.
