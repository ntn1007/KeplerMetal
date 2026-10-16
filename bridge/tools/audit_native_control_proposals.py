#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute bounded control proposals and audit their exact GPU qualifications.

CPU-only; requires the named local, proprietary fixtures. No fixture or binary
is distributed with this source. A passing audit never certifies a hardware
SIMT bound or authorizes automatic allocation for an arbitrary program.
"""
from pathlib import Path
import argparse
from datetime import datetime
import io
import json
import unittest

from analyze_native_control_reserve import analyze
from propose_native_control_reserve import analyze_observations, decode, SOURCE_SHA256
from test_native_control_proposals import ControlProposalTests
from verify_control_flow_delivery import observations, failure
from verify_native_control_reserve import load, sha, require, terminal
from verify_native_reserve_sweep import verify as sweep

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = [
    "control-flow-native-observations-20261015-02",
    "control-flow-entry-observations-20261015",
    "control-reduction-fine-observations-20261015",
    "control-reduction-boundary-observations-20261015",
    "control-reduction-serial-observations-20261015",
    "control-reduction-pressure-observations-20261015",
    "control-reduction-reload-observations-20261015",
    "native-control-generalization-observations-20261016",
    "native-segmented-control-observations-20261016",
]
SOURCES = [
    "propose_native_control_reserve.py", "test_native_control_proposals.py",
    "audit_native_control_proposals.py", "verify_native_reserve_sweep.py",
    "verify_native_control_reserve.py", "verify_control_flow.py",
    "verify_control_flow_delivery.py", "analyze_native_control_reserve.py",
]


def verify(root):
    progress = root / "results/native-control-regions-progress-20261016"
    start = load(progress / "start.json")
    plan = load(progress / "qualification-plan.json")
    saved = load(progress / "proposals-final.json")
    require(start["previous_goal_turn_classification"] == "progress"
            and plan["base_commit"] == start["base_commit"]
            and plan["task_id"] == start["task_id"], "turn and claim provenance")
    for name in SOURCES:
        require(sha(Path(__file__).resolve().parent / name) == sha(root / "tools" / name),
                "current audit checkout differs: " + name)
    require(saved["analyzer_SHA256"] == SOURCE_SHA256
            == sha(root / "tools/propose_native_control_reserve.py")
            and plan["proposals_SHA256"] == sha(progress / "proposals-final.json"), "proposal source pins")
    for name, h in plan["sources_SHA256"].items():
        # A harmless return-schema addition was removed after qualification so
        # historical sweep proofs remain exactly comparable. Keep that version.
        path = (progress / "sweep-verifier-at-qualification.py" if name == "verify_native_reserve_sweep.py"
                else root / "tools" / name)
        require(sha(path) == h, "qualification-time source changed: " + name)
    recomputed = []
    lexical = []
    for name in FOLDERS:
        folder = root / "results" / name
        rows = observations(folder)
        require(len(rows) == len(load(folder / "observations.json")["records"]), "capture completeness")
        recomputed.extend(analyze_observations(folder))
        lexical.extend(analyze(folder, root))
    require(recomputed == saved["records"] and len(recomputed) == saved["profiles"] == 29
            and saved["refused"] == 0 and saved["GPU_work"] == 0
            and not saved["hardware_upper_bound_certified"] and not saved["automatic_runtime_application"],
            "byte-bound proposal recomputation")
    for row in recomputed:
        old = next(x for x in lexical if x["function"] == row["function"]
                   and x["observation_SHA256"] == row["observations_SHA256"])
        require(row["maximum_forward_intervals"] == old["max_forward_join_intervals"]
                and row["region_count"] == old["control_instruction_counts"].get("joinat", 0)
                and row["code_SHA256"] == old["code_SHA256"]
                and not row["hardware_depth_proven"] and not row["automatic_runtime_application"],
                "independent lexical cross-check")
    stream = io.StringIO()
    tests = unittest.TextTestRunner(stream=stream, verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ControlProposalTests))
    require(tests.wasSuccessful() and tests.testsRun == 18, "encoded-word refusal tests")
    portable = load(progress / "portable-tests.json")
    require(portable["exit_code"] == 0 and portable["tests"] == 18 and portable["GPU_work"] == 0
            and portable["source_SHA256"] == SOURCE_SHA256
            and portable["tests_SHA256"] == sha(root / "tools/test_native_control_proposals.py")
            and portable["stdout_SHA256"] == sha(progress / "portable-tests.stdout")
            and portable["stderr_SHA256"] == sha(progress / "portable-tests.stderr"), "recorded portable tests")
    cases = []
    intervals = []
    for row in plan["cases"]:
        native, obs = root / row["native"], root / row["observations"]
        build, result = root / row["build"], root / row["result"]
        ni = load(native / "inputs.json")
        require(sha(native / "inputs.json") == row["native_inputs_SHA256"]
                and sha(obs / "observations.json") == row["observations_SHA256"]
                and sha(native / "assets/control_flow.metallib") == row["library_SHA256"]
                and ni.get("variant", "nested") == row["variant"], "selected native source/library")
        for n, h in ni["source_hashes"].items():
            require(sha(native / n) == h, "original native source: " + n)
        for n, h in ni["assets_SHA256"].items():
            require(sha(native / "assets" / n) == h, "original native asset: " + n)
        proposal = next(x for x in recomputed if x["function"] == row["function"]
                        and x["observations_SHA256"] == row["observations_SHA256"])
        require(proposal == row["proposal"] and proposal["proposed_metadata_control"] == row["reserve"]
                and proposal["code_SHA256"] == row["code_SHA256"], "manual qualification selection")
        proof = sweep(result, build, native, obs, row["reserve"], row["depth"], root,
                      expected_variant=row["variant"])
        require(proof == load(progress / (row["label"] + "-verification-02.json"))
                and proof["numerical_status"] == row["expected_numerical_status"] == "PASS"
                and proof["kernel_dispatches"] == row["planned_kernel_dispatches"] == 12, "new numerical proof")
        run = load(progress / (row["label"] + "-run.json"))
        require(run["exit_code"] == 0 and run["runner_SHA256"] == sha(root / "tools/run_command_ir_runtime.py"),
                "executed runner")
        m = load(result / "execution/manifest.json")
        require(m["GPU_reservation"]["lock_inherited_by_child"], "child GPU lease")
        intervals.append((datetime.fromisoformat(m["started_at"]), datetime.fromisoformat(m["completed_at"])))
        # Stronger4096 results are old data, not new GPU execution by this turn.
        previous = root / "results" / ("native-reserve-v5-" + ("entry" if row["label"] == "entry96" else "reload")
                                      + "-depth96-20261016")
        previous_build = root / "results" / ("native-reserve-v5-" + ("entry" if row["label"] == "entry96" else "reload")
                                            + "-build-20261016")
        terminal(previous, root, previous_build)
        files = sorted((result / "outputs").iterdir())
        require(len(files) == 24 and len(list((previous / "outputs").iterdir())) == 24, "semantic file set")
        require(all(p.read_bytes() == (previous / "outputs" / p.name).read_bytes() for p in files),
                "new proposal differs from existing4096 outputs")
        event = load(result / "results.json")["import"]["events"][0]
        cases.append({"label": row["label"], "source_variant": row["variant"], "result": row["result"],
                      "build": row["build"], "proof": proof, "maximum_abstract_path_depth": proposal["maximum_abstract_path_depth"],
                      "prepared_CRS_relation": proposal["proposed_prepared_CRS_relation"],
                      "decoded_allocation_word40": event["decoded_allocation_word40"],
                      "matching_files_against_archived4096": 24, "archived_GPU_rerun": False})
    intervals.sort()
    require(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])), "overlapping cohorts")
    implicit = load(progress / "implicit-variant-refusal.json")
    require(implicit["status"] == "EXPECTED_REFUSAL" and implicit["GPU_work"] == 0
            and implicit["message"] == "explicit nested-equivalent oracle variant", "implicit variant refusal")
    try:
        row = plan["cases"][1]
        sweep(root / row["result"], root / row["build"], root / row["native"], root / row["observations"],
              row["reserve"], row["depth"], root)
    except ValueError as exc:
        require(str(exc) == implicit["message"], "variant refused for another reason")
    else:
        raise ValueError("implicit variant was accepted")
    archived = sweep(root / "results/native-reserve-rule-d96-r3584-20261016",
                     root / "results/native-reserve-rule-d96-r3584-20261016-build",
                     root / "results/control-flow-native-build-20261015-02",
                     root / "results/control-flow-native-observations-20261015-02", 3584, 96, root)
    require(archived == load(root / "results/native-reserve-rule-d96-r3584-20261016/independent-verification.json"),
            "historical default proof schema or result changed")
    failures = []
    for label, folder, native_name, entry in [
            ("entry96", "control-flow-entry-depth96-20261015", "control-flow-entry-build-20261015", True),
            ("reload96", "control-reduction-reload-depth96-20261015", "control-reduction-reload-build-20261015", False)]:
        result = root / "results" / folder
        terminal(result, root, root / "results" / native_name)
        failures.append({"label": label, "result": folder, "proof": failure(result, entry)})
    layout = load(progress / "layout-counterexamples.json")
    scheduled_targets = boundary_tails = 0
    for row in layout["examples"]:
        obs = root / row["observations"]
        observed = next(x for x in load(obs)["records"] if x["function"] == row["function"])
        capture = obs.parent / row["function"] / "capture"
        listing = (capture / "native.envydis.txt").read_text()
        code = (capture / "native.sass").read_bytes()
        decoded = decode(code, listing, observed["code_SHA256"])
        for item in row["scheduled_targets"]:
            pc, target = int(item["PC"], 16), int(item["target"], 16)
            require(decoded[pc][1] == target and decoded[target][0] == "SCHEDULE", "native schedule target")
            scheduled_targets += 1
        for line in row["placement_mismatches"]:
            pc = int(line[:8], 16)
            require(line in listing and pc % 64 == 0 and decoded[pc][:2] == ("BRANCH", pc), "native boundary tail")
            boundary_tails += 1
    require(scheduled_targets > 0 and boundary_tails == 3, "layout counterexamples")
    library = root / "results/native-allocation-runtime-build-20261016-04"
    manifest = load(library / "manifest.json")
    for n, h in manifest["source_SHA256"].items():
        relative = n if n.startswith("src/") else "src/" + n
        require(sha(library / relative) == h == sha(root / relative), "runtime source changed")
    require(sha(library / "libKeplerMetal.a") == manifest["static_library_SHA256"], "runtime archive changed")
    for n, h in start["reference_sources_SHA256"].items():
        require(sha(root / n) == h, "reference source changed")
    for row in start["system_before"]:
        require(sha(row["path"]) == row["SHA256"], "system file changed")
    require(len(start["system_before"]) == 83
            and sha("/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist") == start["OCLP_SHA256"], "OCLP changed")
    return {"status": "PASS", "scope": "Manual qualification of exact native control proposals; CPU-only audit",
            "base_commit": plan["base_commit"], "source_SHA256": {n: sha(root / "tools" / n) for n in SOURCES},
            "proposals_SHA256": sha(progress / "proposals-final.json"), "analyzed_profiles": 29,
            "CPU_encoded_word_tests": tests.testsRun, "new_cases": cases, "historical_native_failures": failures,
            "historical_original96_r3584": archived, "historical_GPU_rerun": False,
            "schedule_target_counterexamples": scheduled_targets, "boundary_tail_counterexamples": boundary_tails,
            "new_GPU_command_buffers": sum(x["proof"]["GPU_command_buffers"] for x in cases),
            "new_compute_trials": sum(x["proof"]["kernel_dispatches"] for x in cases),
            "new_exact_uint32_results": sum(x["proof"]["exact_uint32_results"] for x in cases),
            "new_invocation_witnesses": sum(t["invocation_witnesses"] for x in cases for t in x["proof"]["trials"]),
            "new_guard_bytes": sum(x["proof"]["guard_bytes"] for x in cases),
            "new_wrong_uint32_results": sum(x["proof"]["wrong_uint32_results"] for x in cases),
            "matching_files_against_archived4096": 48, "overlapping_cohorts": False,
            "runtime_sources_unchanged": len(manifest["source_SHA256"]), "runtime_archive_SHA256": manifest["static_library_SHA256"],
            "system_files_unchanged": 83, "OCLP_unchanged": True,
            "preparation_failure_preserved": sha(progress / "premature-preflight.json"),
            "hardware_upper_bound_certified": False, "automatic_runtime_application": False,
            "new_M1_executions": 0, "new_GPU_launches_by_auditor": 0, "performance_benchmark": False,
            "physical_VRAM_saving_measured": False, "Qwen_job_ids": [], "full_objective_complete": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.lab_root.resolve()
    out = args.out.resolve()
    out.relative_to(root / "results")
    proof = verify(root)
    with out.open("x") as f:
        json.dump(proof, f, indent=2)
        f.write("\n")
    print(json.dumps({k: v for k, v in proof.items()
                      if k not in ["new_cases", "historical_native_failures", "historical_original96_r3584", "source_SHA256"]}, indent=2))
