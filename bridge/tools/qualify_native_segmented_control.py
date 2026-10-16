#!/usr/bin/env python3
"""Run selected bounded segmented-control cases serially with the frozen lease.

Never replays an existing result directory. A prediction mismatch or verifier
failure preserves the process output and stops before the next cohort.
"""
from pathlib import Path
import argparse
import json
import shutil
import sys

from verify_native_control_reserve import sha, load, require
from verify_native_segmented_control import verify_case

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / "results/native-allocation-cfg-progress-20261016"
NATIVE = ROOT / "results/native-segmented-control-build-20261016"
OBS = ROOT / "results/native-segmented-control-observations-20261016"
LIBRARY = ROOT / "results/native-allocation-runtime-build-20261016-04"
CASES = {
    "native96": ("common", "native:depth96", "PASS"),
    "native120": ("common", "native:depth120", "FAIL"),
    "r2048": ("r2048", "reserved:depth120", "FAIL"),
    "r2560": ("r2560", "reserved:depth120", "PASS"),
    "common4096": ("common", "reserved:depth120", "PASS"),
}


def main():
    global ROOT, PROGRESS, NATIVE, OBS, LIBRARY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=list(CASES), nargs="+", required=True)
    parser.add_argument("--lab-root", type=Path, help="Existing bridge tree; also the shared reservation root")
    args = parser.parse_args()
    if args.lab_root:
        ROOT = args.lab_root.resolve()
        PROGRESS = ROOT / "results/native-allocation-cfg-progress-20261016"
        NATIVE = ROOT / "results/native-segmented-control-build-20261016"
        OBS = ROOT / "results/native-segmented-control-observations-20261016"
        LIBRARY = ROOT / "results/native-allocation-runtime-build-20261016-04"
    require(len(args.case) == len(set(args.case)), "duplicate case selection")
    predictions = load(PROGRESS / "experiment-plan.json")["predictions_before_GPU"]
    map_prediction = {"native96": "native_depth96", "native120": "native_depth120",
                      "r2048": "standalone_2048_depth120", "r2560": "standalone_2560_depth120",
                      "common4096": "common_4096_depth120"}
    for case in args.case:
        client, mode, expected = CASES[case]
        require(predictions[map_prediction[case]] == expected, "prediction was not frozen")
        build = ROOT / "results" / f"native-segmented-{client}-client-20261016"
        out = ROOT / "results" / f"native-segmented-{case}-20261016"
        inputs = load(build / "inputs.json")
        require(sha(build / "application") == inputs["executable_SHA256"], "built executable changed")
        for n, h in inputs["source_hashes"].items():
            require(sha(build / n) == h, "built source changed: " + n)
        for n, h in inputs["assets_SHA256"].items():
            require(sha(build / "assets" / n) == h, "built asset changed: " + n)
        for n, h in inputs["runtime_SHA256"].items():
            require(sha(build / "runtime" / n) == h, "frozen launcher changed: " + n)
        out.mkdir(exist_ok=False)
        for n in ["application", "inputs.json", *inputs["source_hashes"]]:
            shutil.copyfile(build / n, out / n)
        shutil.copytree(build / "assets", out / "assets")
        (out / "outputs").mkdir()
        sys.path.insert(0, str(build / "runtime"))
        import run_sdk_host
        import lab_gpu_reservation
        require(sha(run_sdk_host.__file__) == inputs["runtime_SHA256"]["run_sdk_host.py"]
                and sha(lab_gpu_reservation.__file__) == inputs["runtime_SHA256"]["lab_gpu_reservation.py"],
                "loaded launcher identity")
        manifest = run_sdk_host.run_host(out / "application", out / "execution",
                                        [str(out / "assets"), str(out / "outputs"), mode], ROOT)
        shutil.copyfile(out / "execution/execution.stdout", out / "results.json")
        proof = verify_case(out, build, LIBRARY, NATIVE, OBS)
        with (out / "independent-verification.json").open("x") as f:
            json.dump(proof, f, indent=2)
            f.write("\n")
        numerical = proof["numerical"]
        history = {"case": case, "mode": mode, "expected": expected,
                   "numerical_status": numerical["numerical_status"], "PID": manifest["pid"],
                   "root": str(out.relative_to(ROOT)), "build": str(build.relative_to(ROOT)),
                   "manifest_SHA256": sha(out / "execution/manifest.json"),
                   "verification_SHA256": sha(out / "independent-verification.json"),
                   "runner_SHA256": sha(__file__)}
        with (PROGRESS / ("case-" + case + ".json")).open("x") as f:
            json.dump(history, f, indent=2)
            f.write("\n")
        print(json.dumps(history), flush=True)
        require(numerical["numerical_status"] == expected,
                "Prediction mismatch preserved; inspect before another cohort")


if __name__ == "__main__":
    main()
