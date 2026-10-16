#!/usr/bin/env python3
"""Run an explicit allocation/contract matrix serially on the shared lab lease.

The JSON matrix names frozen builds and new result directories. Numerical
failures are accepted only when they match the complete recorded A5 failure
contract. Native API rejection cases submit no command buffers.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

from verify_native_control_reserve import allocation_case, terminal, require, sha, load

ROOT = Path(__file__).resolve().parents[1]
EARLY = {"unaligned", "oversize", "short-metadata", "nil-device"}
LATE = {"wrong-code", "wrong-gpr", "wrong-control", "wrong-frame", "downward", "wrong-function"}


def under_results(value):
    path = (ROOT / value).resolve()
    path.relative_to(ROOT / "results")
    return path


def verify_contract(root, build, mode):
    inp = terminal(root, ROOT, build)
    require(load(build / "inputs.json") == inp, "contract build provenance")
    d = load(root / "results.json")
    require(mode in EARLY | LATE and d["mode"] == mode and d["status"] == "PASS"
            and d["device"] == "NVIDIA GeForce GTX 880M" and d["registry_id"] == 4294968458
            and d["constructor_restored"] and d["rejection_verified"]
            and not d["pipeline_created"] and d["native_recovery_pipeline_created"]
            and d["GPU_command_buffers"] == d["kernel_dispatches"] == 0
            and d["runs"] == [] and d["error"]
            and not d["system_modified"] and not d["performance_benchmark"], "contract result")
    p = d["import"]
    require(d["early_contract"] == (mode in EARLY), "rejection phase")
    if mode in EARLY:
        require(p == {}, "early refusal must not install the constructor")
    else:
        require(p["calls"] == len(p["events"]) == 1 and p["constructor_restored"]
                and not p["contract_verified"] and not p["native_program_replaced"]
                and not p["system_modified"], "native refusal proof")
        e = p["events"][0]
        require(e["parsed"] and not e["certificate_matches"]
                and "only_metadata_words9_11_changed" not in e, "invalid contract patched payload")
        require(e["code_match"] == (mode != "wrong-code" and mode != "wrong-function")
                and e["metadata_match"] == (mode in {"wrong-code", "downward"}),
                "wrong reason for native refusal")
        config = load(root / "assets/control_flow_config.json")
        name = "depth64" if mode == "wrong-function" else "depth96"
        certificate = config["certificates"][name]
        require(e["actual_code_SHA256"] == certificate["code_SHA256"]
                and all(e["actual_metadata_words"][i] == certificate["metadata_words"][i]
                        for i in range(58) if i not in (2, 4)), "refusal native input")
        if mode == "downward":
            require(e["requested_reserve"] == 1024
                    < e["actual_metadata_words"][11], "not a downward refusal")
    return {"mode": mode, "status": "PASS", "phase": "early" if mode in EARLY else "constructor",
            "native_recovery_pipeline_created": True, "GPU_command_buffers": 0,
            "run_manifest_SHA256": sha(root / "execution/manifest.json")}


def verify_case(row):
    root, build = under_results(row["result"]), under_results(row["build"])
    if row["expect"] == "rejection":
        return verify_contract(root, build, row["mode"])
    require(row["expect"] in {"numeric_pass", "unchanged_failure", "no_dispatch"}, "unknown expected outcome")
    outcome = allocation_case(row["depth"], row["reserve"], under_results(row["native"]),
                              under_results(row["observations"]), root=root, build=build,
                              require_post=True, expected_mode=row["mode"])
    if row["expect"] == "unchanged_failure":
        require(outcome["numerical_status"] == "FAIL", "failure control became correct")
    else:
        require(outcome["numerical_status"] == "PASS"
                and outcome["kernel_dispatches"] == (0 if row["expect"] == "no_dispatch" else 12),
                "dispatch expectation")
    return outcome


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    matrix = load(a.matrix)
    out = under_results(a.out)
    out.mkdir(exist_ok=False)
    rows = matrix["cases"]
    require(rows and len({str(under_results(r["result"])) for r in rows}) == len(rows), "duplicate case outputs")
    history = []
    for index, row in enumerate(rows):
        build, result = under_results(row["build"]), under_results(row["result"])
        require(not result.exists(), "result exists; inspect its handle instead of replaying")
        argv = [sys.executable, str(ROOT / "tools/run_command_ir_runtime.py"),
                "--build", str(build), "--out", str(result), "--mode", row["mode"]]
        process = subprocess.run(argv, capture_output=True, text=True)
        (out / f"{index:02d}-run.stdout").write_text(process.stdout)
        (out / f"{index:02d}-run.stderr").write_text(process.stderr)
        record = {"index": index, **row, "exit_code": process.returncode}
        history.append(record)
        (out / "history.json").write_text(json.dumps(history, indent=2) + "\n")
        if process.returncode:
            (out / "status.json").write_text(json.dumps({"status": "FAIL", "case": index, "phase": "execution", "retry": False}) + "\n")
            raise RuntimeError(f"Case{index} stopped; inspect its actual process/manifest. No automatic retry.")
        try:
            record["verification"] = verify_case(row)
        except BaseException:
            (out / "status.json").write_text(json.dumps({"status": "FAIL", "case": index, "phase": "verification", "retry": False}) + "\n")
            raise
        (out / "history.json").write_text(json.dumps(history, indent=2) + "\n")
        print(index, row["expect"], row["mode"], "VERIFIED", flush=True)
    (out / "status.json").write_text(json.dumps({"status": "PASS", "cases": len(rows),
        "matrix_SHA256": sha(a.matrix), "performance_benchmark": False, "full_objective_complete": False}) + "\n")


if __name__ == "__main__":
    main()
