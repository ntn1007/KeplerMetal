#!/usr/bin/env python3
"""Audit recorded native-reserve experiments without launching any GPU work.

The experiment is application-local. Native machine-code captures remain local;
this verifier publishes hashes, numerical counts and bounded conclusions only.
It does not certify arbitrary shaders or the installed compiler/driver globally.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct

from verify_control_flow import verify as numeric, result as cpu_result
from verify_control_flow_delivery import observations

ROOT = Path(__file__).resolve().parents[1]
DRIVER = "2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"
MSL = "2fcb68ca33362c87492a7ab46f6fe0b8a4fe9731e9879c902a553f855a31b02d"
LIBRARY = "d861a84fc1067c87a23ae73beb2755afc82b6ab28895f869950e315f983b8822"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def terminal(root, reservation_root=None, runtime_build=None):
    m = load(root / "execution/manifest.json")
    inp = load(root / "inputs.json")
    require(m["exit_code"] == 0 and not m["SIGKILL_requested"]
            and not m["authoritative_ps_status"]
            and m["GPU_reservation"]["state"] == "terminal", str(root))
    require(sha(root / "application") == inp["executable_SHA256"]
            == m["original_binary_sha256"], "executable provenance")
    require(sha(root / "execution/application") == m["signed_binary_sha256"],
            "signed executable provenance")
    if reservation_root is not None:
        require(Path(m["reservation_root"]) == reservation_root, "reservation root")
    for name, h in inp["source_hashes"].items():
        require(sha(root / name) == h, "frozen source: " + name)
    for name, h in inp["assets_SHA256"].items():
        require(sha(root / "assets" / name) == h, "asset: " + name)
    for name, h in inp.get("runtime_SHA256", {}).items():
        require(runtime_build is not None, "explicit frozen runner build required")
        require(sha(runtime_build / "runtime" / name) == h, "runner: " + name)
        field = {"run_sdk_host.py": "launcher_SHA256",
                 "lab_gpu_reservation.py": "reservation_module_SHA256"}[name]
        require(m[field] == h, "executed runner: " + name)
    require(load(root / "results.json") == load(root / "execution/execution.stdout"),
            "recorded result differs from child stdout")
    return inp


def unchanged_failure(root, depth, runtime_build):
    """Check the exact observed failure, never turn arbitrary exit1 into PASS."""
    terminal(root, ROOT, runtime_build)
    d = load(root / "results.json")
    require(d["depth"] == depth and d["native_reference"]
            and not d["program_replaced"] and not d["CPU_expected_answers_uploaded"]
            and d["device"] == "NVIDIA GeForce GTX 880M"
            and d["registry_id"] == 4294968458 and not d["system_modified"]
            and not d["performance_benchmark"], "native failure identity")
    counts = [1, 31, 32, 33, 64, 128, 256, 512, 1024, 99, 256, 2048]
    locals_ = [1, 31, 32, 33, 64, 128, 256, 512, 1024, 33, 64, 1024]
    require(len(d["runs"]) == len(counts), "failure trial count")
    wrong = invocations = 0
    for trial, row in enumerate(d["runs"]):
        n = counts[trial]
        seed = 0x13579 + trial * 971
        reserved = trial % 3
        require(row["trial"] == trial and row["threads"] == n
                and row["local"] == locals_[trial] and row["seed"] == seed
                and row["reserved"] == reserved and row["stride"] == 129
                and row["groups"] * row["local"] == n
                and row["command_status"] == 4 and row["kernel_dispatches"] == 1,
                "failure dispatch geometry")
        want = bytearray(b"\xa5" * (256 + n * 129 * 4))
        for i in range(n * 129):
            struct.pack_into("<I", want, 128 + 4 * i,
                             ((i * 1664525 + 1013904223) & 0xffffffff) ^ seed)
        require((root / "outputs" / row["input_file"]).read_bytes() == want,
                "failure input/guards")
        output = (root / "outputs" / row["output_file"]).read_bytes()
        require(len(output) == row["output_bytes"] == 256 + n * 16
                and output == b"\xa5" * len(output), "failure output/guards")
        for gid in range(n):
            expected = cpu_result(depth, gid, seed, reserved)
            require(expected != (0xa5a5a5a5,) * 4, "uninformative CPU oracle")
            wrong += sum(v != 0xa5a5a5a5 for v in expected)
        invocations += n
    return {"numerical_status": "FAIL", "trials": 12,
            "kernel_invocations_without_final_result": invocations,
            "incorrect_uint32_values": wrong, "guard_bytes": 6144,
            "output_unchanged_A5": True, "process_terminal": True}


def allocation_case(depth, reserve, native, obs, root=None, build=None,
                    require_post=False, expected_mode=None):
    root = root or ROOT / "results" / f"native-reserve-v4-{depth}-{reserve}-20261015"
    build = build or root.with_name(root.name.replace("-20261015", "-build-20261015"))
    inp = terminal(root, ROOT, build)
    require(load(build / "inputs.json") == inp, "frozen allocation build provenance")
    for name, h in inp["source_hashes"].items():
        require(sha(build / name) == h, "frozen allocation source: " + name)
    require(inp["reserve_mode"] == reserve, "reserve identity")
    require(inp["native_build_inputs_SHA256"] == sha(native / "inputs.json")
            and inp["observations_SHA256"] == sha(obs / "observations.json"),
            "allocation source observation pins")
    ni = load(native / "inputs.json")
    require(inp["assets_SHA256"]["control_flow.metallib"]
            == ni["assets_SHA256"]["control_flow.metallib"], "native library pin")
    config = load(root / "assets/control_flow_config.json")
    function = "depth" + str(depth)
    record = next(r for r in load(obs / "observations.json")["records"]
                  if r["function"] == function)
    certificate = config["certificates"][function]
    require(certificate["code_SHA256"] == record["code_SHA256"]
            and certificate["metadata_words"] == record["metadata_words"],
            "certificate differs from native observation")
    d = load(root / "results.json")
    require(d["driver_SHA256"] == DRIVER and d["mode"] == (expected_mode or function)
            and d["depth"] == depth and d["native_reference"]
            and not d["program_replaced"] and not d["system_modified"]
            and not d["CPU_expected_answers_uploaded"], "allocation experiment scope")
    proof = d["import"]
    require(proof["contract_verified"] and proof["constructor_restored"]
            and not proof["native_program_replaced"] and not proof["system_modified"]
            and proof["calls"] == len(proof["events"]) == 1, "constructor proof")
    event = proof["events"][0]
    for flag in ["certificate_matches", "metadata_match", "code_match", "parsed",
                 "only_metadata_words9_11_changed", "native_code_identical",
                 "decoded_contract_verified"]:
        require(event[flag] is True, "constructor assertion: " + flag)
    if require_post:
        for flag in ["native_code_identical_after_constructor",
                     "payload_unchanged_after_constructor"]:
            require(event[flag] is True, "post-constructor assertion: " + flag)
        require(event["post_constructor_code_SHA256"] == event["actual_code_SHA256"]
                and all(len(event[key]) == 64 for key in ["patched_payload_SHA256",
                        "input_snapshot_SHA256"]), "post-constructor hashes")
    w = event["actual_metadata_words"]
    require(len(w) == 58 and all(w[i] == certificate["metadata_words"][i]
                                for i in range(58) if i not in (2, 4)),
            "unpinned stable metadata")
    requested = {"0": 0, "round": (w[11] + 511) & ~511, "4096": 4096}[reserve]
    new_control = requested or w[11]
    expected = ((w[12] + 15) & ~15) * 64 + ((new_control + 511) & ~511) + 512
    require(event["requested_reserve"] == requested
            and event["old_control"] == w[11] and event["new_control"] == new_control
            and new_control >= w[11] and w[9] == 64 * w[12] + w[11]
            and event["native_frame"] == w[12] and event["native_GPR"] == w[7]
            and event["decoded_allocation_word40"] == expected
            == event["expected_allocation_word40"]
            and event["decoded_spill_bytes56"] == w[14]
            and event["actual_code_SHA256"] == record["code_SHA256"]
            and event["code_bytes"] == record["code_bytes"]
            and event["metadata_sections"] == event["code_sections"] == 1,
            "decoded allocation contract")
    if reserve == "4096":
        outcome = numeric(root)
        outcome.pop("files_SHA256")
        outcome["numerical_status"] = outcome.pop("status")
    else:
        outcome = unchanged_failure(root, depth, build)
    return {"depth": depth, "reserve_mode": reserve, "old_word11": w[11],
            "new_word11": new_control, "native_frame": w[12],
            "decoded_allocation_word40": expected, "native_code_bytes": event["code_bytes"],
            "native_code_SHA256": record["code_SHA256"], "constructor_restored": True,
            "code_unchanged_in_constructor_payload": True,
            "post_constructor_identity_checked": require_post,
            "source_SHA256": inp["source_hashes"],
            "run_manifest_SHA256": sha(root / "execution/manifest.json"), **outcome}


def m1_reference(folder, supplied):
    files = load(folder / "RESULT_MANIFEST.json")["files"]
    for name, h in files.items():
        require(sha(folder / name) == h, "M1 collected file: " + name)
    provenance = load(folder / "results/provenance.json")
    require(provenance["architecture"] == "arm64" and not provenance["system_modified"]
            and not provenance["performance_benchmark"]
            and provenance["MSL_SHA256"] == MSL
            and provenance["source_manifest_SHA256"] == sha(folder / "FILE_MANIFEST.json"),
            "M1 source/provenance")
    library_hash = sha(folder / "build/assets/control_flow.metallib")
    commands = load(folder / "build/commands.json")
    require(all(c["exit_code"] == 0 for c in commands), "M1 build failure")
    if supplied:
        require(provenance["supplied_library"] is True
                and provenance["input_metallib_SHA256"] == LIBRARY == library_hash
                == sha(folder / "input26.metallib"), "same iMac library required")
        require([c["label"] for c in commands] == ["host"], "supplied library recompiled")
    else:
        # The earlier runner predates the supplied_library provenance field.
        # Its recorded successful Metal build establishes this different route.
        require([c["label"] for c in commands] == ["metal", "metallib", "host"],
                "source reference must compile its own library")
    cases = []
    adaptations = []
    for mode in ["depth0", "depth64", "depth96", "no_dispatch-depth96"]:
        root = folder / "results" / mode
        terminal(root)
        require(sha(root / "assets/control_flow.metallib") == library_hash,
                "M1 case library identity")
        case = numeric(root, apple_reference=True)
        case.pop("files_SHA256")
        cases.append(case)
        d = load(root / "results.json")
        changes = [{"trial": r["trial"], "requested": r["requested_local"],
                    "actual": r["local"]} for r in d["runs"]
                   if r["requested_local"] != r["local"]]
        if changes:
            adaptations.append({"mode": mode, "max_threads": d["max_threads"],
                                "adapted_group_sizes": changes})
    return {"status": "PASS", "collected_files_verified": len(files),
            "manifest_SHA256": sha(folder / "RESULT_MANIFEST.json"),
            "MSL_SHA256": MSL, "input_metallib_SHA256": library_hash,
            "same_iMac_library_bytes": supplied, "architecture": "arm64",
            "macOS": provenance["macOS"].strip(), "host_SDK": provenance["SDK"],
            "cases": cases, "group_geometry_adaptations": adaptations,
            "SM30_execution": False, "performance_benchmark": False}


def verify():
    base = ROOT / "results"
    progress = base / "control-flow-reduction-progress-20261015"
    native = base / "control-flow-native-build-20261015-02"
    original_obs = base / "control-flow-native-observations-20261015-02"
    fine = base / "control-reduction-fine-build-20261015"
    fine_obs = base / "control-reduction-fine-observations-20261015"
    # These readers reparse the raw private native containers and native variants.
    observed = {"original": observations(original_obs), "fine": observations(fine_obs),
                "boundary": observations(base / "control-reduction-boundary-observations-20261015"),
                "serial": observations(base / "control-reduction-serial-observations-20261015"),
                "pressure": observations(base / "control-reduction-pressure-observations-20261015"),
                "reload": observations(base / "control-reduction-reload-observations-20261015")}
    require(sha(native / "control_flow.metal") == MSL
            and sha(native / "assets/control_flow.metallib") == LIBRARY,
            "default source/native library identity")
    reductions = []
    for label, depth in [("fine", n) for n in range(65, 72)] + [
            ("boundary", n) for n in [72, 80, 88]] + [("reload", 96)]:
        root = base / f"control-reduction-{label}-depth{depth}-20261015"
        build = base / f"control-reduction-{label}-build-20261015"
        reductions.append({"variant": label, "depth": depth,
                           **unchanged_failure(root, depth, build)})
    controls = []
    for label, depths in [("serial", [96]), ("pressure", [32, 64, 96])]:
        for depth in depths:
            root = base / f"control-reduction-{label}-depth{depth}-20261015"
            terminal(root, ROOT, base / f"control-reduction-{label}-build-20261015")
            record = numeric(root)
            record.pop("files_SHA256")
            if label == "pressure":
                # The generic oracle's third output counts scalar values here,
                # not loop iterations. Avoid a misleading published field name.
                record["folded_scalar_values"] = record.pop("loop_body_visits")
                record["scalar_values_per_thread"] = depth * 8
            controls.append(record)
    cases = [allocation_case(depth, reserve, n, o)
             for depth, n, o in [(65, fine, fine_obs), (96, native, original_obs)]
             for reserve in ["0", "round", "4096"]]
    for depth in [65, 96]:
        selected = [r for r in cases if r["depth"] == depth]
        require(len({r["native_code_SHA256"] for r in selected}) == 1,
                "native code must match across allocation-only A/B controls")
    references = [m1_reference(progress / "m1-cap/Reference", False),
                  m1_reference(progress / "m1-air26/Reference", True)]
    start = load(progress / "start.json")
    for row in start["system_before"]:
        require(sha(row["path"]) == row["SHA256"], "system file changed: " + row["path"])
    require(len(start["system_before"]) == 83
            and sha("/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist")
            == start["OCLP_SHA256"], "OCLP provenance")
    return {"status": "PASS", "scope": "Offline verification of recorded GPU observations",
            "new_GPU_executions_by_this_verifier": 0,
            "base_commit": start["base_commit"], "observations": observed,
            "original_native_reductions": reductions, "separate_native_controls": controls,
            "allocation_only_experiments": cases,
            "corrected_positive_trials": 24, "unchanged_code_failing_control_trials": 48,
            "corrected_exact_uint32_results": sum(r.get("exact_uint32_results", 0) for r in cases),
            "corrected_kernel_invocation_witnesses": sum(r.get("kernel_invocation_witnesses", 0) for r in cases),
            "allocation_experiment_guard_bytes": sum(r["guard_bytes"] for r in cases),
            "M1_references": references, "system_files_unchanged": 83, "OCLP_unchanged": True,
            "performance_benchmark": False, "Qwen_job_ids": [], "full_objective_complete": False,
            "limits": ["Two native program profiles corrected inside the test process only",
                       "Metadata words2/4 vary; their incoming bytes are preserved and their meanings remain unknown",
                       "Code identity is checked in the constructor payload, not an independent resident instruction capture",
                       "4096 is a tested reserve, not a minimal or universal allocation formula",
                       "Unmodified native65/96 remain defective; no installed compiler/driver repair",
                       "M1 uses the same library input but a different GPU backend and some smaller threadgroups"],
            "next": "Qualify conservative native allocation profiles and rejection controls before shared runtime integration"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.relative_to(ROOT / "results")
    data = verify()
    with out.open("x") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    print(json.dumps({k: data[k] for k in ["status", "corrected_positive_trials",
          "unchanged_code_failing_control_trials", "corrected_exact_uint32_results",
          "corrected_kernel_invocation_witnesses", "allocation_experiment_guard_bytes",
          "system_files_unchanged", "OCLP_unchanged", "full_objective_complete"]}, indent=2))
