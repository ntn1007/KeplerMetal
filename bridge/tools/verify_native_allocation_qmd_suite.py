#!/usr/bin/env python3
"""Audit the bounded native-QMD cohort from frozen bytes, without GPU work.

Requires the named local fixtures. No captured packet, executable, driver or
compiled GPU program is distributed with this verifier. Refusal controls mutate
copies in memory only; malformed commands are never submitted to the device.
"""
from pathlib import Path
import argparse
from datetime import datetime
import json
import re
import struct

from analyze_native_allocation_qmd import analyze, decode_stream, packets, u64
from verify_native_allocation_qmd_execution import verify as execution
from verify_native_control_reserve import load, require, sha, terminal

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / "results/native-allocation-qmd-progress-20261016"
REFERENCE_SHA = "8a4ad7edaf88f26bd90fe8bd06353e2b7b7f6703b570e475a7fae7c4da7ab80c"
REFERENCE_COMMIT = "9fdf5c4062007929d9f4e6cbad9c9771fe61b880"
LAB_SHA = "5636b0d0d158fc985bf9b1df5fd0e16b91909a9a6f48423c175272b7fe4ddb67"
PUBLIC_SHA = "9e26d4eb78b772585ae312e1e4ca1a72ef432f02935674ff7f67600cd4488a3c"


def reference():
    pinned = load(PROGRESS / "official-QMD-reference.json")
    layout = load(PROGRESS / "QMD-layout-source.json")
    header = PROGRESS / "reference-cla0c0qmd.h"
    require(pinned["commit"] == REFERENCE_COMMIT
            and pinned["SHA256"] == layout["SHA256"] == REFERENCE_SHA == sha(header)
            and pinned["bytes"] == header.stat().st_size
            and pinned["url"] == "https://raw.githubusercontent.com/NVIDIA/open-gpu-doc/"
            + REFERENCE_COMMIT + "/classes/compute/cla0c0qmd.h",
            "official QMD reference pin")
    candidates = [ROOT / layout["path"], ROOT.parent / layout["path"]]
    local = [p for p in candidates if p.is_file()]
    require(len(local) == 1 and sha(local[0]) == REFERENCE_SHA,
            "local Mesa QMD header identity")
    fields = {}
    for name, span in layout["fields"].items():
        match = re.search(r"^#define\s+NVA0C0_QMDV00_06_" + name
                          + r"\s+MW\((\d+):(\d+)\)\s*$", header.read_text(), re.M)
        require(match is not None, "QMD field absent: " + name)
        high, low = map(int, match.groups())
        require(span == {"high_bit": high, "low_bit": low}, "QMD field range: " + name)
        fields[name] = span
    require(len(fields) == 9, "QMD reference coverage")
    return {"commit": REFERENCE_COMMIT, "SHA256": REFERENCE_SHA,
            "url": pinned["url"], "field_ranges": fields,
            "local_Mesa_header_identical": True}


def refusal_controls(root):
    d = load(root / "results.json")
    cert = load(root / "assets/allocation-depth104.json")
    w = cert["metadata_words"]
    original = (root / "outputs" / d["records"][0]["file"]).read_bytes()
    frame = (w[12] + 15) & ~15
    args = [d, frame, w[7], w[11], d["decoded_allocation_word40"],
            u64(struct.pack("<32I", *d["variant_after_words_0_128"]), 16)]
    decode_stream(original, *args)
    parsed = packets(original)
    q = parsed[5]["data"]
    controls = []

    def reject(name, raw, arguments, message):
        try:
            decode_stream(raw, *arguments)
        except ValueError as exc:
            require(str(exc) == message, name + ": wrong refusal: " + str(exc))
            controls.append({"case": name, "status": "EXPECTED_REFUSAL", "gate": message})
        else:
            raise ValueError(name + ": malformed fixture accepted")

    def xor_word(offset, mask):
        raw = bytearray(original)
        value, = struct.unpack_from("<I", raw, offset)
        struct.pack_into("<I", raw, offset, value ^ mask)
        return raw

    reject("truncated", original[:-4], args, "unknown stream length")
    reject("unknown_method", xor_word(0, 1), args, "unknown native packet sequence")
    reject("wrong_subchannel", xor_word(0, 1 << 13), args, "push header")
    reject("wrong_QMD_version", xor_word(q + 0x48, 1), args, "QMD format/geometry/binding identity")
    reject("wrong_parameter_address", xor_word(q + 0x84, 1), args, "QMD format/geometry/binding identity")
    reject("wrong_register_count", xor_word(q + 0xb8, 1 << 24), args, "QMD local/CRS fields")
    reject("wrong_CRS", xor_word(q + 0xbc, 512), args, "QMD local/CRS fields")
    reject("wrong_QMD_upload_target", xor_word(parsed[3]["data"] + 12, 256), args,
           "native QMD/constant upload and launch headers")
    reject("wrong_constant_buffer_mask", xor_word(q + 0x50, 128), args,
           "QMD format/geometry/binding identity")
    reject("wrong_program_offset", xor_word(q + 0x20, 8), args,
           "program offset differs from observed variant low32")
    changed = list(args)
    changed[4] += 512
    reject("wrong_decoded_budget", original, changed, "QMD fields do not reproduce decoded allocation")
    changed = list(args)
    changed[0] = {**d, "count": 98}
    reject("wrong_geometry_contract", original, changed, "QMD format/geometry/binding identity")
    reject("wrong_local_high", xor_word(q + 0xb8, 16), args, "QMD local/CRS fields")
    reject("unexpected_shared_memory", xor_word(q + 0x44, 1), args, "QMD format/geometry/binding identity")
    require(len(controls) == 14, "refusal count")
    return {"status": "PASS", "valid_control": "ACCEPTED", "cases": controls,
            "source_stream_SHA256": sha(root / "outputs" / d["records"][0]["file"]),
            "mutated_commands_submitted": 0}


def verify(public_library):
    base = ROOT / "results"
    lab = base / "native-allocation-runtime-build-20261016-04"
    require(sha(lab / "libKeplerMetal.a") == LAB_SHA
            and sha(public_library / "libKeplerMetal.a") == PUBLIC_SHA, "unchanged archive pins")
    start = load(PROGRESS / "start.json")
    prepared = []
    submitted = []
    intervals = []
    builds = [(base / "native-allocation-qmd-capture-build-20261016-03",
               base / "native-allocation-generalization-client-build-20261016", lab),
              (base / "native-allocation-qmd-execute-build-20261016",
               base / "native-allocation-generalization-client-build-20261016", lab),
              (base / "native-allocation-qmd-public-execute-build-20261016",
               base / "native-allocation-public-generalization-client-build-20261016", public_library)]
    for build, parent, library in builds:
        inp = load(build / "inputs.json")
        require(inp["parent_client_inputs_SHA256"] == sha(parent / "inputs.json")
                and all(c["exit_code"] == 0 for c in load(build / "commands.json")), "client build")
        for name, h in inp["source_hashes"].items():
            current = ROOT / ("src" if name.endswith(".h") else "tools") / name
            require(sha(current) == h == sha(build / name), "current/frozen client text: " + name)
        for name, h in inp["assets_SHA256"].items():
            require(sha(build / "assets" / name) == h == sha(parent / "assets" / name), "parent asset")

    def record(root, build, library, proof, stored):
        require(proof == load(stored), "stored verification changed: " + root.name)
        m = load(root / "execution/manifest.json")
        intervals.append((datetime.fromisoformat(m["started_at"]),
                          datetime.fromisoformat(m["completed_at"]), root.name))
        return {"root": str(root.relative_to(ROOT)), "build": str(build.relative_to(ROOT)),
                "manifest_SHA256": sha(root / "execution/manifest.json"),
                "recorded_results_SHA256": sha(root / "results.json"),
                "verification_SHA256": sha(stored), "verification": proof}

    capbuild = builds[0][0]
    for depth in [104, 120]:
        for mode in ["native", "reserved"]:
            root = base / f"native-allocation-qmd-{mode}{depth}-20261016-03"
            proof = analyze(root, capbuild, lab, ROOT)
            prepared.append(record(root, capbuild, lab, proof, root / "independent-verification.json"))
    exbuild = builds[1][0]
    for depth in [104, 120]:
        for mode in ["native", "reserved"]:
            root = base / f"native-allocation-qmd-execute-{mode}{depth}-20261016"
            stored = (PROGRESS / "execute-reserved104-verification.json" if depth == 104 and mode == "reserved"
                      else root / "independent-verification.json")
            proof = execution(root, exbuild, lab, ROOT)
            require(proof["numerical_status"] == ("PASS" if mode == "reserved" else "FAIL"), "paired outcome")
            if mode == "native":
                require(all(r["numerical_status"] == "UNCHANGED_OUTPUT"
                            and r["other_wrong_words"] == r["invocation_witnesses"] == 0
                            for r in proof["records"]), "specific retained native failure")
            submitted.append(record(root, exbuild, lab, proof, stored))
    public_root = base / "native-allocation-qmd-public-execute-reserved120-20261016"
    proof = execution(public_root, builds[2][0], public_library, ROOT)
    require(proof["numerical_status"] == "PASS", "public artifact result")
    submitted.append(record(public_root, builds[2][0], public_library, proof,
                            PROGRESS / "public-execute-reserved120-verification.json"))

    pairs = []
    for depth in [104, 120]:
        cases = [r["verification"] for r in prepared if r["verification"]["function"] == f"depth{depth}"]
        a, b = cases
        require(a["mode"] == "native" and b["mode"] == "reserved"
                and a["native_frame"] == b["native_frame"]
                and a["certificate_code_SHA256"] == b["certificate_code_SHA256"], "paired native code/frame")
        aq, bq = a["records"][0], b["records"][0]
        comparable = ["version", "major_version", "groups", "local", "shared_bytes",
                      "local_low_bytes", "local_high_bytes", "register_count"]
        require(all(aq[k] == bq[k] for k in comparable)
                and aq["CRS_bytes"] == 3072 and bq["CRS_bytes"] == 4608
                and b["decoded_allocation_word40"] - a["decoded_allocation_word40"] == 1536,
                "paired QMD memory relation")
        for actual in [r["verification"] for r in submitted if r["verification"]["function"] == f"depth{depth}"]:
            wanted = aq if actual["mode"] == "native" else bq
            for r in actual["records"]:
                require(all(r["QMD"][k] == wanted[k] for k in comparable + ["CRS_bytes"]), "submitted QMD pair")
        pairs.append({"function": f"depth{depth}", "native_code_SHA256": a["certificate_code_SHA256"],
                      "local_low_bytes": aq["local_low_bytes"], "local_high_bytes": aq["local_high_bytes"],
                      "register_count": aq["register_count"], "native_CRS_bytes": 3072,
                      "corrected_CRS_bytes": 4608, "native_allocation": a["decoded_allocation_word40"],
                      "corrected_allocation": b["decoded_allocation_word40"]})
    ordered = sorted(intervals)
    require(all(a[0] <= a[1] <= b[0] for a, b in zip(ordered, ordered[1:])), "cohorts overlapped")

    failed = base / "native-allocation-qmd-capture-build-20261016-02"
    require(not (failed / "application").exists()
            and any(c["exit_code"] != 0 for c in load(failed / "commands.json")), "preserved build failure")
    preliminary = base / "native-allocation-qmd-native104-20261016"
    terminal(preliminary, ROOT, base / "native-allocation-qmd-capture-build-20261016")
    require(load(preliminary / "results.json")["user_GPU_command_buffers"] == 0, "preliminary scope")

    for name, h in start["runtime_before_SHA256"].items():
        require(sha(ROOT / "src" / name) == h == sha(public_library / "src" / name), "runtime modified: " + name)
    require(sha(ROOT / "tools/native_command_capture.mm") == start["original_capture_source_SHA256"],
            "previous capture tool modified")
    for r in start["system_before"]:
        require(sha(r["path"]) == r["SHA256"], "system file changed: " + r["path"])
    require(len(start["system_before"]) == 83
            and sha("/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist") == start["OCLP_SHA256"], "OCLP changed")
    totals = {k: sum(r["verification"][k] for r in submitted) for k in [
        "user_GPU_command_buffers", "compute_trials", "blit_command_buffers", "exact_uint32_results",
        "incorrect_uint32_results", "invocation_witnesses", "guard_bytes", "parameter_bytes_checked"]}
    require(totals == {"user_GPU_command_buffers": 45, "compute_trials": 15, "blit_command_buffers": 30,
                       "exact_uint32_results": 3564, "incorrect_uint32_results": 2376, "invocation_witnesses": 891,
                       "guard_bytes": 7680, "parameter_bytes_checked": 7680}, "cohort totals")
    sources = ["native_allocation_qmd_capture.mm", "native_allocation_qmd_execute.mm",
               "build_native_allocation_qmd_capture.py", "analyze_native_allocation_qmd.py",
               "verify_native_allocation_qmd_execution.py", Path(__file__).name]
    for name in sources:
        require(sha(Path(__file__).resolve().parent / name) == sha(ROOT / "tools" / name),
                "audit checkout differs from laboratory tool: " + name)
    return {"status": "PASS", "scope": "Offline audit of bounded prior GPU and uncommitted observations",
            "new_GPU_executions_by_verifier": 0, "base_commit": start["base_commit"],
            "source_SHA256": {n: sha(ROOT / "tools" / n) for n in sources},
            "official_reference": reference(), "prepared_only": prepared, "submitted": submitted,
            "paired_memory_fields": pairs, "offline_refusal_controls": refusal_controls(base / "native-allocation-qmd-native104-20261016-03"),
            "totals": totals, "prepared_only_QMDs": 12, "captured_then_committed_QMDs": 15,
            "correct_compute_trials": 9, "retained_numerical_failure_trials": 6,
            "cohorts_serialized": True, "excluded_preliminary_uncommitted_QMDs": 3,
            "preserved_CPU_build_failure": {"root": str(failed.relative_to(ROOT)), "GPU_work": 0,
                                           "commands_SHA256": sha(failed / "commands.json")},
            "lab_archive_SHA256": LAB_SHA, "public_archive_SHA256": PUBLIC_SHA,
            "system_files_unchanged": 83, "OCLP_unchanged": True, "runtime_unchanged": True,
            "Qwen_job_ids": [], "new_M1_executions": 0, "performance_benchmark": False,
            "resident_QMD_readback": False, "driver_commit_rewrites_excluded": False,
            "general_allocation_rule_proven": False, "full_objective_complete": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lab-root", type=Path, help="Existing bridge tree containing the frozen cohort and shared lease")
    p.add_argument("--public-library", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.lab_root:
        ROOT = args.lab_root.resolve()
        PROGRESS = ROOT / "results/native-allocation-qmd-progress-20261016"
    out = args.out.resolve()
    out.relative_to(ROOT / "results")
    proof = verify(args.public_library.resolve())
    with out.open("x") as f:
        json.dump(proof, f, indent=2)
        f.write("\n")
    print(json.dumps({k: proof[k] for k in ["status", "totals", "correct_compute_trials",
          "retained_numerical_failure_trials", "system_files_unchanged", "OCLP_unchanged", "full_objective_complete"]}, indent=2))
