#!/usr/bin/env python3
"""Audit segmented native experiments with explicit oracle/factory contracts.

No GPU launch. Standalone lower-reserve experiments and common-runtime API
qualification are reported separately. Function suffixes are total source
levels; simultaneous source nesting is the maximum segment length.
"""
from pathlib import Path
import argparse
import hashlib
import json

from native_segmented_control import configuration, source, result, iterative_result, SEGMENTS, EXPERIMENT, DRIVER
from verify_native_control_reserve import load, sha, require
from verify_native_allocation_common import allocation_proof
from verify_native_allocation_qmd_execution import verify as execution

ROOT = Path(__file__).resolve().parents[1]


def standalone_proof(proof, library, certificate, reserve):
    c = load(certificate)
    w = c["metadata_words"]
    require(proof["backend"] == "standalone_experiment" and proof["requested_reserve"] == reserve
            and proof["library_SHA256"] == sha(library) == c["library_sha256"]
            and proof["certificate_SHA256"] == sha(certificate)
            and c["intent"] == "native_control_reservation_experiment"
            and c["control_reserve"] == reserve and reserve in [2048, 2560]
            and c["driver_sha256"] == DRIVER, "standalone experimental identity")
    p = proof["standalone"]
    require(p["contract_verified"] and p["constructor_restored"]
            and not p["native_program_replaced"] and not p["system_modified"]
            and p["calls"] == len(p["events"]) == 1, "standalone constructor contract")
    e = p["events"][0]
    for flag in ["certificate_matches", "metadata_match", "code_match", "parsed",
                 "only_metadata_words9_11_changed", "native_code_identical",
                 "native_code_identical_after_constructor", "payload_unchanged_after_constructor",
                 "decoded_contract_verified"]:
        require(e[flag] is True, "standalone assertion: " + flag)
    actual = e["actual_metadata_words"]
    require(len(actual) == 58 and all(actual[i] == w[i] for i in range(58) if i not in [2, 4]),
            "standalone stable metadata")
    require(e["requested_reserve"] == e["new_control"] == reserve >= e["old_control"] == w[11]
            and e["native_frame"] == w[12] == w[13] and e["native_GPR"] == w[7]
            and e["code_bytes"] == c["code_bytes"]
            and e["actual_code_SHA256"] == e["post_constructor_code_SHA256"] == c["native_code_sha256"]
            and e["decoded_allocation_word40"] == e["expected_allocation_word40"]
            == ((w[12] + 15) & ~15) * 64 + reserve + 512
            and e["decoded_spill_bytes56"] == w[14]
            and e["metadata_sections"] == e["code_sections"] == 1
            and len(e["input_snapshot_SHA256"]) == len(e["patched_payload_SHA256"]) == 64,
            "standalone decoded code/allocation evidence")


def verify_case(root, build, library, native_build, observations, reservation_root=None):
    reservation_root = reservation_root or ROOT
    inp = load(build / "inputs.json")
    ni = load(native_build / "inputs.json")
    od = load(observations / "observations.json")
    require(inp == load(root / "inputs.json")
            and inp["native_build_inputs_SHA256"] == sha(native_build / "inputs.json")
            == od["native_build_inputs_SHA256"]
            and inp["observations_SHA256"] == sha(observations / "observations.json")
            and od["driver_SHA256"] == DRIVER and ni["variant"] == "segmented"
            and ni["segments"] == configuration()["segments"]
            and (native_build / "segmented_control.metal").read_text() == source(),
            "segmented native generation/observation pins")
    for name, h in ni["source_hashes"].items():
        require(sha(native_build / name) == h, "native frozen source: " + name)
    for name, h in ni["assets_SHA256"].items():
        require(sha(native_build / "assets" / name) == h, "native frozen asset: " + name)
    require(load(root / "assets/segmented-control.json") == configuration()
            and sha(root / "assets/control_flow.metallib") == ni["assets_SHA256"]["control_flow.metallib"],
            "segmented semantic assets")
    d = load(root / "results.json")
    total = int(d["function"][5:])
    require(total in SEGMENTS, "unknown segmented function")
    native_record = next(r for r in od["records"] if r["function"] == d["function"])
    manifest = load(root / "assets/native-allocation-manifest.json")
    certificate = root / "assets" / manifest["certificates"][d["function"]]["file"]
    c = load(certificate)
    require(c["metadata_words"] == native_record["metadata_words"]
            and c["native_code_sha256"] == native_record["code_SHA256"]
            == sha(observations / d["function"] / "capture/native.sass")
            and c["code_bytes"] == native_record["code_bytes"], "segmented certificate native identity")
    for trial in range(3):
        seed, reserved = 0x13579 + trial * 971, trial % 3
        for gid in range(99):
            require(result(total, gid, seed, reserved) == iterative_result(SEGMENTS[total], gid, seed, reserved),
                    "segmented independent oracle disagreement")
    backend, reserve = inp["allocation_backend"], inp["requested_reserve"]
    validator = allocation_proof
    commands = load(build / "commands.json")
    require(all(r["exit_code"] == 0 for r in commands), "client build failure")
    if backend == "common":
        require(reserve == 4096 and inp["standalone_object_SHA256"] is None
                and c["intent"] == "native_control_reservation"
                and [r["label"] for r in commands] == ["client"], "common API build contract")
    else:
        require(backend == "standalone" and reserve in [2048, 2560]
                and inp["source_hashes"]["NativeControlReserveExperiment.mm"] == EXPERIMENT
                and sha(build / "standalone.o") == inp["standalone_object_SHA256"]
                and [r["label"] for r in commands] == ["standalone", "client"], "standalone build contract")
        validator = lambda p, l, c: standalone_proof(p, l, c, reserve)
    numeric = execution(root, build, library, reservation_root, oracle=result,
                        import_validator=validator, control_reserve=reserve)
    return {"scope": "Bounded segmented native control, not a general allocator",
            "segments": SEGMENTS[total], "total_source_levels": total,
            "maximum_simultaneous_source_nesting": max(SEGMENTS[total]),
            "allocation_backend": backend, "static_library_linked": inp["static_library_SHA256"],
            "common_allocation_API_used": backend == "common" and numeric["mode"] == "reserved",
            "native_observation_and_certificate_code_SHA256": c["native_code_sha256"],
            "native_build_inputs_SHA256": sha(native_build / "inputs.json"),
            "observations_SHA256": sha(observations / "observations.json"),
            "numerical": numeric, "performance_benchmark": False, "full_objective_complete": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ["root", "build", "library", "native-build", "observations", "out"]:
        p.add_argument("--" + n, type=Path, required=True)
    p.add_argument("--reservation-root", type=Path)
    a = p.parse_args()
    reservation = (a.reservation_root or ROOT).resolve()
    out = a.out.resolve()
    out.relative_to(reservation / "results")
    proof = verify_case(a.root.resolve(), a.build.resolve(), a.library.resolve(),
                        a.native_build.resolve(), a.observations.resolve(), reservation)
    with out.open("x") as f:
        json.dump(proof, f, indent=2)
        f.write("\n")
    print(json.dumps({k: v for k, v in proof.items() if k != "numerical"}, indent=2))
    print(json.dumps({k: v for k, v in proof["numerical"].items() if k not in ["records", "files_SHA256"]}, indent=2))
