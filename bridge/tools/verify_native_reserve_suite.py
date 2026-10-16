#!/usr/bin/env python3
"""Recompute the recorded native-reserve qualification; never launch GPU work."""
from pathlib import Path
import argparse
import hashlib
import json

from qualify_native_reserve import verify_case, under_results
from verify_native_control_reserve import load, sha, require, observations, DRIVER

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / "results/native-reserve-qualification-progress-20261016"


def verify():
    start = load(PROGRESS / "start.json")
    require(start["previous_goal_turn_classification"] == "progress", "previous turn audit")
    pins = load(PROGRESS / "qualification-source-pins.json")
    for name, h in pins.items():
        require(sha(PROGRESS / ("v5-frozen-" + name)) == h, "initial source text: " + name)
        if name != "build_native_reserve_experiment.py":
            require(sha(ROOT / "tools" / name) == h, "qualified source changed: " + name)
    builder_sources = [PROGRESS / "v5-frozen-build_native_reserve_experiment.py",
                       PROGRESS / "v5-diversity-build_native_reserve_experiment.py",
                       PROGRESS / "v5-lifetime-build_native_reserve_experiment.py"]
    builder_hashes = {sha(p) for p in builder_sources}
    require(len(builder_hashes) == 3 and sha(ROOT / "tools/build_native_reserve_experiment.py")
            == sha(builder_sources[-1]), "builder revision provenance")
    groups = [("preflight", "preflight"), ("qualification", "qualification"),
              ("diversity", "diversity"), ("lifetime", "lifetime")]
    checked = []
    observed = {}
    builds = {}
    for matrix_name, suite_name in groups:
        matrix_path = PROGRESS / (matrix_name + "-matrix.json")
        suite = ROOT / "results" / ("native-reserve-v5-" + suite_name + "-suite-20261016")
        matrix = load(matrix_path)
        status = load(suite / "status.json")
        history = load(suite / "history.json")
        require(status["status"] == "PASS" and status["matrix_SHA256"] == sha(matrix_path)
                and len(history) == status["cases"] == len(matrix["cases"]), "suite completeness")
        for index, (row, record) in enumerate(zip(matrix["cases"], history)):
            require(record["index"] == index and record["exit_code"] == 0
                    and all(record[k] == v for k, v in row.items()), "matrix/history identity")
            outcome = verify_case(row)
            require(outcome == record["verification"], "independently recomputed outcome changed")
            root, build = under_results(row["result"]), under_results(row["build"])
            inp = load(build / "inputs.json")
            require(inp["source_hashes"]["NativeControlReserveExperiment.mm"]
                    == pins["NativeControlReserveExperiment.mm"]
                    and inp["source_generator_SHA256"] in builder_hashes, "candidate source identity")
            for name, h in inp["source_hashes"].items():
                require(sha(ROOT / "tools" / name) == h, "published source differs: " + name)
            builds[row["build"]] = {"inputs_SHA256": sha(build / "inputs.json"),
                                   "executable_SHA256": inp["executable_SHA256"],
                                   "module_object_SHA256": sha(build / "reserve.o"),
                                   "builder_SHA256": inp["source_generator_SHA256"]}
            d = load(root / "results.json")
            require(d["driver_SHA256"] == DRIVER, "result driver identity")
            if matrix_name == "lifetime":
                require(inp["lifetime_probe"] is True, "lifetime host build")
                for flag in ["caller_metadata_overwritten", "caller_hash_overwritten",
                             "factory_autorelease_pool_drained"]:
                    require(d["import"][flag] is True, "lifetime precondition: " + flag)
            if row["expect"] != "rejection" and row["observations"] not in observed:
                observed[row["observations"]] = observations(under_results(row["observations"]))
            if outcome.get("variant") == "pressure":
                outcome["folded_scalar_values"] = outcome.pop("loop_body_visits")
            checked.append({"group": matrix_name, "expected": row["expect"],
                            "result": row["result"], **outcome})
    require(len(checked) == 35 and len(builds) == 14, "qualification cohort count")
    positives = [r for r in checked if r["expected"] == "numeric_pass"]
    failures = [r for r in checked if r["expected"] == "unchanged_failure"]
    missing = [r for r in checked if r["expected"] == "no_dispatch"]
    rejections = [r for r in checked if r["expected"] == "rejection"]
    require(len(positives) == 19 and len(failures) == 4 and len(missing) == 2
            and len(rejections) == 10, "outcome partition")
    require(len({r["native_code_SHA256"] for r in positives}) == 17, "distinct native code profiles")
    for depth in [65, 96]:
        causal = [r for r in checked if r.get("depth") == depth
                  and r["group"] in {"qualification", "preflight"}]
        require(len({r["native_code_SHA256"] for r in causal}) == 1, "causal code changed")
    # Native baseline outputs, M1 semantics and changed-source variants are
    # compared byte-for-byte separately from the CPU arithmetic oracle.
    matched = []
    results = ROOT / "results"
    pairs = []
    for depth in [0, 64]:
        pairs.append((results / f"native-reserve-v5-depth{depth}-20261016",
                      results / f"control-flow-extended-20261015-depth{depth}"))
    m1 = results / "control-flow-reduction-progress-20261015/m1-air26/Reference"
    for depth in [0, 64, 96]:
        pairs.append((results / f"native-reserve-v5-depth{depth}-20261016",
                      m1 / "results" / f"depth{depth}"))
    for label in ["reload", "entry"]:
        pairs.append((results / f"native-reserve-v5-{label}-depth96-20261016",
                      results / "native-reserve-v5-depth96-20261016"))
    for label in ["pressure", "serial"]:
        pairs.append((results / f"native-reserve-v5-{label}-depth96-20261016",
                      results / f"control-reduction-{label}-depth96-20261015"))
    for label in ["original", "pressure"]:
        reference = (results / "native-reserve-v5-depth96-20261016" if label == "original"
                     else results / "native-reserve-v5-pressure-depth96-20261016")
        pairs.append((results / f"native-reserve-v5-{label}-lifetime-depth96-20261016", reference))
    for left, right in pairs:
        files = sorted((left / "outputs").iterdir())
        require(len(files) == 24, "full semantic output file count")
        for p in files:
            require(p.read_bytes() == (right / "outputs" / p.name).read_bytes(), "semantic pair: " + p.name)
        matched.append({"candidate": left.name, "reference": right.name, "matching_files": 24})
    # M1 evidence is historical, not a new M1 or SM30 execution in this cohort.
    for name, h in load(m1 / "RESULT_MANIFEST.json")["files"].items():
        require(sha(m1 / name) == h, "historical M1 reference modified")
    for row in start["system_before"]:
        require(sha(row["path"]) == row["SHA256"], "system file modified")
    require(len(start["system_before"]) == 83
            and sha("/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist")
            == start["OCLP_SHA256"], "OCLP modified")
    runtime = results / "control-flow-runtime-library-build-20261015"
    lm = load(runtime / "manifest.json")
    require(sha(runtime / "libKeplerMetal.a") == lm["static_library_SHA256"]
            and sha(ROOT / "src/KeplerNativeCAS.mm") == lm["source_SHA256"]["src/KeplerNativeCAS.mm"],
            "shared runtime changed")
    return {"status": "PASS", "scope": "Bounded process-local native allocation correction qualification",
            "base_commit": start["base_commit"], "candidate_source_SHA256": pins["NativeControlReserveExperiment.mm"],
            "builds": builds, "cases": checked, "native_observations": observed,
            "distinct_native_program_profiles": 17,
            "positive_GPU_trials": sum(r["trials"] for r in positives),
            "positive_exact_uint32_results": sum(r["exact_uint32_results"] for r in positives),
            "positive_invocation_witnesses": sum(r["kernel_invocation_witnesses"] for r in positives),
            "failing_causal_comparison_trials": sum(r["trials"] for r in failures),
            "no_dispatch_control_trials": sum(r["trials"] for r in missing),
            "actual_pre_dispatch_rejection_cases": len(rejections),
            "API_rejection_GPU_command_buffers": 0,
            "guard_bytes": sum(r.get("guard_bytes", 0) for r in checked),
            "lifetime_GPU_trials": sum(r["trials"] for r in positives if r["group"] == "lifetime"),
            "semantic_file_pairs": matched, "matching_files_across_pairs": sum(p["matching_files"] for p in matched),
            "largest_tested_native_code_bytes": max(r["native_code_bytes"] for r in positives),
            "largest_tested_native_spill_frame": max(r["native_frame"] for r in positives),
            "shared_runtime_unchanged_SHA256": lm["static_library_SHA256"],
            "system_files_unchanged": 83, "OCLP_unchanged": True,
            "new_M1_executions": 0, "Qwen_job_ids": [], "performance_benchmark": False,
            "full_objective_complete": False,
            "limits": ["17 developer-pinned native program profiles, not arbitrary library qualification",
                       "Code and complete input payload identity checked after constructor, not resident instruction capture",
                       "4096 remains a tested reserve, not a general/minimal allocation rule",
                       "API refusals prove rejection/restoration and native PSO recovery; no GPU recovery kernel in those cases",
                       "Lifetime probes drain the factory pool and overwrite caller inputs; general concurrent use remains unqualified",
                       "Shared runtime and installed driver are unchanged; this is explicit level1 integration"],
            "next": "Factor the validated allocator into the common MRC transport with its shared lock, thread-local scope and artifact-specific regression tests"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    out.relative_to(ROOT / "results")
    data = verify()
    with out.open("x") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(json.dumps({k: v for k, v in data.items() if k not in
          {"builds", "cases", "native_observations", "semantic_file_pairs"}}, indent=2))
