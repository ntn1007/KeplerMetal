# Native allocation fields in prepared Kepler commands

The allocation correction now has a bounded command-level observation. Read-only snapshots of our own native compute encoder identify QMDv00_06 local-memory and CRS fields. The same host also captures commands before ordinary Metal submission, then compares private-buffer results with a CPU oracle. No packet is patched or replayed.

This is branch A investigation and explicit level 2 application integration. The common runtime and both qualified archives are unchanged. A general allocator, installed-driver repair and transparent support for arbitrary applications remain open. [Scalar validation summary](native-allocation-qmd-validation.json) · [API](NATIVE_ALLOCATION_API.md).

## Observed fields

| Native function | Local LOW / HIGH, bytes each | GPRs | Original CRS | Corrected CRS | Original decoded budget | Corrected decoded budget |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Source nesting 104 | 1,904 / 1,904 | 63 | 3,072 | 4,608 | 124,928 | 126,464 |
| Source nesting 120 | 2,208 / 2,208 | 63 | 3,072 | 4,608 | 144,384 | 145,920 |

For these profiles, prepared fields follow:

```text
LOW = HIGH = align16(native_frame)
CRS = align512(metadata_word11) + 512
decoded_budget = (LOW + HIGH) * 32 + CRS
```

The API's requested metadata reserve of 4,096 therefore produces a **prepared CRS field of 4,608**, including the observed extra 512 bytes. These are command fields and a decoded variant budget, not measured physical VRAM consumption. The native frame, GPR count and constructor-payload code identity are preserved; LOW and HIGH retain their original values. The known variant fields stay stable across encoding and completion.

The decoder first requires the entire 464-byte, nine-packet native sequence, expected upload sizes and targets, subchannel, QMD version 6 / major 0, three groups of 33 threads, constant-buffer bindings and sizes, and zero shared memory. It checks the QMD program-offset field against the observed variant address's low 32 bits. It then interprets the memory fields; it does not search arbitrary byte streams for plausible numbers.

The field names and bit ranges match NVIDIA's public [QMD header at commit 9fdf5c4062007929d9f4e6cbad9c9771fe61b880](https://github.com/NVIDIA/open-gpu-doc/blob/9fdf5c4062007929d9f4e6cbad9c9771fe61b880/classes/compute/cla0c0qmd.h), SHA-256 `8a4ad7edaf88f26bd90fe8bd06353e2b7b7f6703b570e475a7fae7c4da7ab80c`. The locally consulted Mesa header is byte-identical. QMDv00_06 is a NVIDIA command format, not a Metal API generation.

## Qualification and retained failures

- Four uncommitted cohorts provide **12 prepared QMDs** and submit zero user command buffers.
- Five submitted cohorts provide **15 captured-then-committed QMDs**, 15 compute submissions and 30 separate initialization/readback blit command buffers: **45 user command buffers total**.
- Nine corrected trials return **3,564 exact uint32 values**, including 891 invocation witnesses. Six original native trials retain **2,376 incorrect A5 canary words**. All 7,680 checked input/output guard bytes and 7,680 parameter bytes are intact.
- The public seven-object archive independently passes its three corrected source-120 trials: 1,188 exact values. Its result is distinguished from the six-object lab archive.
- Fourteen offline refusal controls cover truncation, packet method/subchannel, QMD version, bindings, upload target, GPR/CRS/local/shared fields, program offset, geometry and decoded-budget mismatches. Mutated commands stay in CPU memory and are never submitted.

Each submitted trial uses fresh private input/output buffers, deterministic CPU input and A5 initialization, native DMA upload, one ordinary compute dispatch, completion, and native DMA readback. Expected answers are computed offline and never uploaded. Terminal state, signed executable, frozen sources/assets, launcher/reservation modules, archive hashes, constructor evidence, captures and numerical results are rechecked. Cohort timestamps are nonoverlapping.

One earlier uncommitted preflight contains three additional QMDs and is excluded from these totals. A separate host compile failure, fixed by including `<initializer_list>`, is preserved and performed no GPU work. No failed GPU observation is discarded or relabeled as a successful computation.

Archive identities:

- Lab six-object: `5636b0d0d158fc985bf9b1df5fd0e16b91909a9a6f48423c175272b7fe4ddb67`.
- Public seven-object: `9e26d4eb78b772585ae312e1e4ca1a72ef432f02935674ff7f67600cd4488a3c`.

## Reproduction

The source tools are published; raw packets, compiled shaders, archives, executables and private result fixtures are excluded. Regenerate the native source-104/120 library and observation/certificates following [the threshold workflow](NATIVE_ALLOCATION_THRESHOLDS.md). Late builders still require the specified qualified archive, frozen asset client and launcher modules. A complete fresh-checkout regeneration of all those prerequisites is not claimed.

From `bridge/`, with `KP_LAB_BRIDGE` set to the existing shared laboratory bridge root and `KP_QMD_LIBRARY` to its qualified archive directory:

```sh
python3 tools/build_native_allocation_qmd_capture.py \
  --library "$KP_QMD_LIBRARY" \
  --client-build "$KP_LAB_BRIDGE/results/native-allocation-generalization-client-build-20261016" \
  --out results/qmd-build-fresh --execute
```

Omit `--execute` to build the uncommitted capture host. Building never runs it. The following explicit execution uses the frozen signed launcher and the existing shared lease; choose a new result name on every run:

```sh
python3 - <<'PY'
from pathlib import Path
import json, os, shutil, sys
bridge = Path.cwd()
build = bridge / "results/qmd-build-fresh"
result = bridge / "results/qmd-run-fresh"
inputs = json.loads((build / "inputs.json").read_text())
result.mkdir(exist_ok=False)
for name in ["application", "inputs.json", *inputs["source_hashes"]]:
    shutil.copyfile(build / name, result / name)
shutil.copytree(build / "assets", result / "assets")
(result / "outputs").mkdir()
sys.path.insert(0, str(build / "runtime"))
from run_sdk_host import run_host
run_host(result / "application", result / "execution",
         [str(result / "assets"), str(result / "outputs"), "reserved:depth120"],
         Path(os.environ["KP_LAB_BRIDGE"]))
shutil.copyfile(result / "execution/execution.stdout", result / "results.json")
PY
python3 tools/verify_native_allocation_qmd_execution.py \
  --root results/qmd-run-fresh --build results/qmd-build-fresh \
  --library "$KP_QMD_LIBRARY" --reservation-root "$KP_LAB_BRIDGE" \
  --out "$KP_LAB_BRIDGE/results/qmd-run-fresh-verification.json"
```

The capture-only host uses the same launcher but no commit; inspect it with `analyze_native_allocation_qmd.py`. Native comparison modes are `native:depth104` and `native:depth120`; their observed numerical failures must be retained explicitly. Never retry a timeout until the exact process and lease are resolved.

With the complete named original lab fixtures and `KP_PUBLIC_LIBRARY` pointing at the separately qualified public archive, the aggregate audit is CPU-only:

```sh
python3 tools/verify_native_allocation_qmd_suite.py \
  --lab-root "$KP_LAB_BRIDGE" --public-library "$KP_PUBLIC_LIBRARY" \
  --out "$KP_LAB_BRIDGE/results/qmd-suite-fresh-verification.json"
```

## Limits and next investigation

The captures precede commit. Correct GPU results correlate with these prepared fields, but independent resident-QMD readback was not performed and internal commit-time rewriting is not excluded. A completed original command buffer with unchanged output does not establish that the shader started or identify an overflow. The constructor's code checks are not an independent capture of resident instructions.

The full objective is incomplete. The next allocation investigation must relate native control-flow requirements to the prepared CRS field, using discriminating program shapes and bounded evidence. Four earlier threshold pairs and these two profiles do not establish a universal formula or the dynamic hardware stack depth. Video, display, power, full-VRAM behavior and transparent application integration remain separate outstanding work. The 83 tracked system files and OCLP are unchanged. No new M1 execution, performance benchmark, speedup or VRAM saving is claimed.
