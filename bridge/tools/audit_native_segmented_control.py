#!/usr/bin/env python3
"""Re-audit segmented control, old discriminating controls and unchanged system.

CPU-only. Requires named private fixtures; no packet, native shader or driver
binary is included. A tested threshold pair is not a general allocator rule.
"""
from pathlib import Path
import argparse
import ast
from datetime import datetime
import json

from native_segmented_control import configuration, source, SEGMENTS
from verify_native_control_reserve import load, sha, require
from verify_native_segmented_control import verify_case
from verify_native_reserve_sweep import verify as old_sweep
from analyze_native_control_reserve import analyze

ROOT = Path(__file__).resolve().parents[1]


def functions(text):
    return {n.name: ast.dump(n, include_attributes=False)
            for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}


def verify(lab_root):
    root = lab_root
    base = root / "results"
    progress = base / "native-allocation-cfg-progress-20261016"
    start = load(progress / "start.json")
    require(start["previous_goal_turn_classification"] == "progress", "previous turn classification")
    library = base / "native-allocation-runtime-build-20261016-04"
    native = base / "native-segmented-control-build-20261016"
    obs = base / "native-segmented-control-observations-20261016"
    ni = load(native / "inputs.json")
    require(ni["variant"] == "segmented" and ni["segments"] == configuration()["segments"]
            and (native / "segmented_control.metal").read_text() == source()
            and all(r["exit_code"] == 0 for r in load(native / "commands.json")), "native build")
    oracle = load(progress / "oracle-checks.json")
    require(oracle["status"] == "PASS" and oracle["total_cases"] == 1234
            and oracle["generated_MSL_SHA256"] == sha(native / "segmented_control.metal")
            and oracle["new_oracle_source_SHA256"] == sha(native / "builder.py")
            and oracle["old_oracle_source_SHA256"] == sha(root / "tools/verify_control_flow.py")
            and functions((native / "builder.py").read_text())
            == functions((root / "tools/native_segmented_control.py").read_text()),
            "frozen/current builder and oracle functions differ")
    regression = load(progress / "default-verifier-regression.json")
    require(regression["status"] == "PASS" and len(regression["cases"]) == 5
            and not regression["GPU_rerun"], "default verifier regression")
    od = load(obs / "observations.json")
    require(od["native_build_inputs_SHA256"] == sha(native / "inputs.json"), "native observer input")
    intervals = []
    for row in od["records"]:
        case = obs / row["function"]
        m = load(case / "execution/manifest.json")
        d = load(case / "execution/execution.stdout")
        signed = Path(m["signed_executable"]).resolve()
        signed.relative_to(case.resolve() / "execution")
        require(m["exit_code"] == 0 and not m["SIGKILL_requested"] and not m["authoritative_ps_status"]
                and m["GPU_reservation"]["state"] == "terminal" and m["GPU_reservation"]["lock_inherited_by_child"]
                and m["original_binary_sha256"] == ni["capture_executable_SHA256"] == sha(native / "compiler_output_trace")
                and sha(signed) == m["signed_binary_sha256"]
                and d["pipeline_created"] and not d["gpu_dispatch"] and len(d["captures"]) == 1,
                "native observer terminal/source identity")
        intervals.append((datetime.fromisoformat(m["started_at"]), datetime.fromisoformat(m["completed_at"])))
    static = analyze(obs, root)
    require(static == load(progress / "segmented-static-analysis.json")["records"], "raw listing analysis")
    cases = []
    for label, prediction in [("native96", "PASS"), ("native120", "FAIL"),
                              ("r2048", "FAIL"), ("r2560", "PASS"), ("common4096", "PASS")]:
        history = load(progress / ("case-" + label + ".json"))
        run, build = root / history["root"], root / history["build"]
        proof = verify_case(run, build, library, native, obs, root)
        require(proof == load(run / "independent-verification.json")
                and history["verification_SHA256"] == sha(run / "independent-verification.json")
                and history["manifest_SHA256"] == sha(run / "execution/manifest.json")
                and history["runner_SHA256"] == sha(progress / "qualified-runner.py")
                and proof["numerical"]["numerical_status"] == history["numerical_status"] == prediction
                == history["expected"], "case identity or prediction")
        if prediction == "FAIL":
            require(all(r["numerical_status"] == "UNCHANGED_OUTPUT" and r["other_wrong_words"] == 0
                        and r["invocation_witnesses"] == 0 for r in proof["numerical"]["records"]),
                    "retained failure differs from unchanged output")
        inp = load(build / "inputs.json")
        for name, h in inp["source_hashes"].items():
            if name not in ["builder.py", "KeplerNativeAllocation.h"]:
                require(sha(root / "tools" / name) == h, "current/frozen host source: " + name)
        require(functions((build / "builder.py").read_text())
                == functions((root / "tools/native_segmented_control.py").read_text()), "client generator changed")
        m = load(run / "execution/manifest.json")
        intervals.append((datetime.fromisoformat(m["started_at"]), datetime.fromisoformat(m["completed_at"])))
        cases.append({"case": label, "root": history["root"], "build": history["build"],
                      "verification_SHA256": history["verification_SHA256"], "proof": proof})
    intervals.sort()
    require(all(a[0] <= a[1] <= b[0] for a, b in zip(intervals, intervals[1:])), "observer/compute overlap")
    positive = [r["proof"]["numerical"] for r in cases if r["proof"]["numerical"]["numerical_status"] == "PASS"]
    failed = [r["proof"]["numerical"] for r in cases if r["proof"]["numerical"]["numerical_status"] == "FAIL"]
    require(len(positive) == 3 and len(failed) == 2, "new cohort partition")
    low = next(r for r in cases if r["case"] == "r2560")
    high = next(r for r in cases if r["case"] == "common4096")
    for a, b in zip(low["proof"]["numerical"]["records"], high["proof"]["numerical"]["records"]):
        require(a["QMD"]["CRS_bytes"] == 3072 and b["QMD"]["CRS_bytes"] == 4608
                and a["QMD"]["local_low_bytes"] == b["QMD"]["local_low_bytes"] == 928
                and a["QMD"]["local_high_bytes"] == b["QMD"]["local_high_bytes"] == 928,
                "reservation-only QMD comparison")
    for trial in range(3):
        for suffix in ["input", "output", "parameters"]:
            name = f"trial-{trial}-{suffix}.bin"
            require((root / low["root"] / "outputs" / name).read_bytes()
                    == (root / high["root"] / "outputs" / name).read_bytes(), "different transport semantics")

    old_native = base / "native-control-generalization-build-20261016"
    old_obs = base / "native-control-generalization-observations-20261016"
    old_control = base / "native-allocation-rule-progress-20261016"
    historical = []
    for history_name, reserve, expected in [("new-lower-controls-history.json", 3584, "FAIL"),
                                             ("generalization-history.json", 4096, "PASS")]:
        row = next(r for r in load(old_control / history_name) if r["depth"] == 120 and r["reserve"] == reserve)
        old = old_sweep(root / row["result"], root / row["build"], old_native, old_obs, reserve, 120, root)
        require(old == load(root / row["result"] / "independent-verification.json")
                and old["numerical_status"] == expected, "old full120 control changed")
        historical.append({"root": row["result"], "reserve": reserve, "numerical_status": expected,
                           "code_SHA256": old["native_code_SHA256"], "native_frame": old["native_frame"],
                           "trials": old["kernel_dispatches"], "GPU_rerun": False})
    old_static = analyze(old_obs, root)
    old_full = next(r for r in old_static if r["source_depth"] == 120)
    split = next(r for r in static if r["source_depth"] == 120)
    require(old_full["control_instruction_counts"]["joinat"] == 242
            and split["control_instruction_counts"]["joinat"] == 244
            and old_full["max_forward_join_intervals"] == 241
            and split["max_forward_join_intervals"] == 131, "discriminating shape comparison")
    for name, h in start["runtime_before_SHA256"].items():
        require(sha(root / "src" / name) == h == sha(library / "src" / name), "runtime changed: " + name)
    for path, h in start["reference_sources_SHA256"].items():
        require(sha(root / path) == h, "Mesa reference modified")
    for row in start["system_before"]:
        require(sha(row["path"]) == row["SHA256"], "system modified: " + row["path"])
    require(len(start["system_before"]) == 83
            and sha("/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist") == start["OCLP_SHA256"], "OCLP changed")
    keys = ["user_GPU_command_buffers", "compute_trials", "blit_command_buffers", "exact_uint32_results",
            "incorrect_uint32_results", "invocation_witnesses", "guard_bytes", "parameter_bytes_checked"]
    totals = {k: sum(r["proof"]["numerical"][k] for r in cases) for k in keys}
    require(totals == {"user_GPU_command_buffers": 45, "compute_trials": 15, "blit_command_buffers": 30,
                       "exact_uint32_results": 3564, "incorrect_uint32_results": 2376,
                       "invocation_witnesses": 891, "guard_bytes": 7680, "parameter_bytes_checked": 7680}, "cohort totals")
    prototype = load(progress / "stack-model-prototype.json")
    require(prototype["prototype_SHA256"] == sha(progress / "stack_model_prototype.py")
            and len(prototype["cases"]) == 7 and not prototype["allocator_integration_allowed"], "model boundaries")
    source_names = ["native_segmented_control.py", "native_segmented_reserve_probe.mm",
                    "verify_native_segmented_control.py", "qualify_native_segmented_control.py",
                    "audit_native_segmented_control.py", "verify_native_allocation_qmd_execution.py",
                    "verify_native_reserve_sweep.py", "analyze_native_control_reserve.py"]
    for name in source_names:
        require(sha(Path(__file__).resolve().parent / name) == sha(root / "tools" / name), "audit checkout differs: " + name)
    return {"status": "PASS", "scope": "Segmented native control and discriminating archived controls",
            "base_commit": start["base_commit"], "source_SHA256": {n: sha(root / "tools" / n) for n in source_names},
            "oracle_cases": oracle["total_cases"], "oracle_vectors_SHA256": oracle["reference_vectors_SHA256"],
            "frozen_builder_SHA256": sha(native / "builder.py"), "current_builder_functions_identical": True,
            "executed_runner_SHA256": sha(progress / "qualified-runner.py"), "static": static, "cases": cases,
            "historical_full120_controls": historical, "historical_GPU_rerun": False,
            "old_default_verifier_regression": regression, "totals": totals,
            "correct_compute_trials": 9, "retained_failed_compute_trials": 6,
            "simultaneous_cohorts": False, "matching_low_common_data_files": 9,
            "shape_comparison": {"total_source_levels": 120, "full_joinat_count": 242,
                                 "segmented_joinat_count": 244, "full_forward_intervals": 241,
                                 "segmented_forward_intervals": 131, "segmented_source_nesting": 65,
                                 "segmented_PASS_requested_reserve": 2560, "segmented_FAIL_requested_reserve": 2048,
                                 "full_FAIL_requested_reserve": 3584, "full_PASS_requested_reserve": 4096,
                                 "general_minimum_formula_proven": False},
            "prototype_not_hardware_certificate": True, "new_M1_executions": 0,
            "new_GPU_launches_by_this_auditor": 0, "performance_benchmark": False,
            "physical_VRAM_saving_measured": False, "resident_QMD_readback": False,
            "commit_rewrites_independently_excluded": False, "system_files_unchanged": 83,
            "OCLP_unchanged": True, "runtime_unchanged": True, "lab_archive_SHA256": sha(library / "libKeplerMetal.a"),
            "Qwen_job_ids": [], "full_objective_complete": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lab-root", type=Path, default=ROOT)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    lab = a.lab_root.resolve()
    out = a.out.resolve()
    out.relative_to(lab / "results")
    proof = verify(lab)
    with out.open("x") as f:
        json.dump(proof, f, indent=2)
        f.write("\n")
    print(json.dumps({k: proof[k] for k in ["status", "totals", "correct_compute_trials",
          "retained_failed_compute_trials", "shape_comparison", "system_files_unchanged", "full_objective_complete"]}, indent=2))
