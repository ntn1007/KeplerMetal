# Sequential segments distinguish native control requirements

A new bounded experiment separates the total amount of source control flow from its simultaneous nesting. Two consecutive nested blocks of 65 and 55 levels contain 120 source loops, but at most 65 source levels are nested at once. Their unchanged NVIDIA program passes with a tested metadata reserve of 2,560, while the previous fully nested program with 120 levels failed at 3,584 and passed at 4,096. These are observed settings, not universal or exact minimum allocations.

The segmented program has 244 `joinat` instructions, compared with 242 in the fully nested program. Total instruction count alone therefore does not explain these different sufficient reservations. Forward-interval overlap is 131 versus 241; that remains a static listing metric, not independently measured hardware stack depth. [Scalar summary](native-segmented-control-validation.json) · [QMD mapping](NATIVE_ALLOCATION_QMD.md).

This is branch A investigation. It extends the qualified native program shapes and preserves NVIDIA code. It does not introduce an automatic allocator, replace the installed compiler/driver, or add a Metal API.

## New GPU observations

Function suffixes in this cohort name **total source levels**. `depth120` means 65 + 55. A separate configuration, library hash, native code hash and CPU oracle distinguish it from the previous fully nested function.

Here a source level counts one loop and its bounded-child pattern. It does not count every conditional in the generated source and does not denote a hardware stack entry.

| Source segments | Factory / requested metadata control | Prepared CRS, bytes | Numerical outcome |
| --- | --- | ---: | --- |
| 48 + 48 | Native / original 1,312 | 2,048 | PASS, 3 trials |
| 65 + 55 | Native / original 1,584 | 2,560 | FAIL, 3 trials retained |
| 65 + 55 | Standalone experiment / 2,048 | 2,560 | FAIL, 3 trials retained |
| 65 + 55 | Standalone experiment / 2,560 | 3,072 | PASS, 3 trials |
| 65 + 55 | Common allocation API / 4,096 | 4,608 | PASS, 3 trials |

The 2,048 setting changes the constructor metadata but rounds to the same prepared CRS as the original program; it does not correct the output. With 2,560, CRS increases to 3,072 and the results pass. Local LOW/HIGH stay 928 bytes each and GPR count stays 63 through these 65 + 55 comparisons. The decoded budgets are 61,952, 62,464 and 64,000 for CRS 2,560, 3,072 and 4,608 respectively. These are prepared fields and decoded budgets, not measured physical VRAM consumption.

The 48 + 48 program has 39,552 native code bytes and a 584-byte unaligned frame (LOW/HIGH 592 each). The 65 + 55 program has 50,432 code bytes and a 928-byte frame. Both use 63 GPRs. Native frame and code differ from the previous fully nested program, so cross-program comparisons must retain that distinction. Within each reservation comparison the constructor code and frame stay pinned.

The five new cohorts contain 15 compute submissions plus 30 initialization/readback blit command buffers, **45 user command buffers**. Nine trials pass, including three unmodified native trials and six allocation-corrected trials: **3,564 exact uint32 values and 891 invocation witnesses**. Six failing trials retain **2,376 incorrect A5 words**. All 7,680 guard bytes and 7,680 parameter bytes are intact. The lower-reserve experiment and the common API produce nine identical input/output/parameter files.

All cases use three full groups of 33 threads, three deterministic seed/parameter selections and fresh private input/output buffers per trial. The shader performs at most twice its total number of source levels: no more than 240 loop-body visits per invocation. Expected answers are never uploaded. Commands are captured read-only before ordinary commit, without packet editing or replay.

Only the six-object lab archive `5636b0d0d158fc985bf9b1df5fd0e16b91909a9a6f48423c175272b7fe4ddb67` receives these new GPU observations. It is linked unchanged in all clients. The standalone 2,048/2,560 factory uses the separately pinned experimental MRC object; it is not the common API. The common 4,096 case uses `KPCreateCertifiedNativeAllocationPipeline`. No new segmented GPU qualification is attributed to the separate public seven-object archive.

## Checks and source reproduction

Two native compiler observers create pipelines without dispatch and capture metadata/code for both functions. Every decoded listing word is checked against native bytes. The CPU reference has two implementations: recursive nesting and an explicit event stack. Their 1,234 comparisons include 300 matches against the previous single-block oracle, 240 against its serial mode, 594 new qualified invocation vectors and 100 other partitions. The new vectors deliberately differ from the fully nested program's answers.

The previous full120 controls at 3,584 and 4,096 are re-audited from raw data without GPU replay. Five previous QMD cohorts also retain identical numerical verification after the offline verifier gains explicit oracle/import-validator parameters. Default verification stays pinned to its original common-API contract and explicitly refuses non-nested assets unless an appropriate oracle is supplied. A CPU-only refusal check on the new positive dataset distinguishes that mismatch from a GPU numerical failure.

The sources needed to regenerate the new native library, capture its metadata and build a client are included. They require Xcode/Metal, the existing pinned restored driver, the signed laboratory launcher, and the source-built envytools disassembler described in [the threshold workflow](NATIVE_ALLOCATION_THRESHOLDS.md). A common runtime archive can be built using [the public source builder](BUILDING.md); a new archive receives a new identity and needs its own GPU qualification.

From the single laboratory `bridge/` tree, choose **new output names** and use the existing host reservation. Example generation and client commands:

```sh
python3 tools/native_segmented_control.py native \
  --out results/segmented-native-fresh
python3 tools/observe_control_flow.py \
  --build results/segmented-native-fresh --out results/segmented-observations-fresh
python3 tools/native_segmented_control.py client \
  --native-build results/segmented-native-fresh \
  --observations results/segmented-observations-fresh \
  --library "$KP_QMD_LIBRARY" --backend standalone --reserve 2560 \
  --out results/segmented-client-fresh
```

Use `--backend common --reserve 4096` for the common API, or `--backend standalone --reserve 2048` for the retained rounding comparison. The builder never launches GPU work. Launch the chosen client with the frozen `run_sdk_host.run_host` procedure in [the QMD reproduction guide](NATIVE_ALLOCATION_QMD.md), substituting its new build/result names and choosing `native:depth96`, `native:depth120` or `reserved:depth120`. Then use the segmented oracle explicitly:

```sh
python3 tools/verify_native_segmented_control.py \
  --root results/segmented-run-fresh --build results/segmented-client-fresh \
  --native-build results/segmented-native-fresh \
  --observations results/segmented-observations-fresh \
  --library "$KP_QMD_LIBRARY" --reservation-root "$KP_LAB_BRIDGE" \
  --out "$KP_LAB_BRIDGE/results/segmented-run-fresh-verification.json"
```

The included `qualify_native_segmented_control.py` preserves the original five-case lab plan and fixture names; it refuses existing result directories. It is not a fresh-name automatic bootstrap. The aggregate `audit_native_segmented_control.py --lab-root ... --out ...` is CPU-only and requires the complete named historical fixtures, including initial system hashes and old full120controls. Those private binary trees are omitted. The source-only numerical tests run with `python3 -m unittest discover -s tests -v` on ordinary Python without Metal.

## Limits and next step

A bounded single-control-path model was explored on seven old listings. It terminates on those inputs, but omits actual warp masks, predicate dataflow and divergent-branch tokens. It is explicitly rejected as a hardware-depth certificate and is not integrated into allocation. Mesa's structured-NIR stack and CRS formula are a reference from a different compiler; they do not certify NVIDIA binaries.

These two new program shapes support investigating simultaneously live control regions rather than using total source loops or total `joinat` count as a necessary reservation. They do not prove a general upper bound, exact minimum, dynamic hardware depth, resident-QMD identity or exclusion of internal commit-time rewriting. The public tools retain refusal and provenance checks; no heuristic automatically changes arbitrary shaders.

The next step is a conservative, explicitly bounded control-flow estimator with unsupported forms rejected before integration. Full hardware coverage and transparent application integration remain incomplete, including video, display, power and sustained full-VRAM behavior. The runtime, 83 tracked system files and OCLP are unchanged. No new M1 run, performance benchmark, speedup or physical VRAM saving is claimed.
