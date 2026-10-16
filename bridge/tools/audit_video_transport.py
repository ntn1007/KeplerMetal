#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the bounded video investigation without starting native/GPU programs.

Requires the named private laboratory evidence, including separately obtained
proprietary dependencies. Public output contains hashes and counts, not binaries,
pixels, stack dumps, credentials or private host configuration.
"""
from pathlib import Path
import argparse
import base64
import datetime
import hashlib
import json
import plistlib
import re

from verify_native_control_reserve import terminal

ROOT = Path(__file__).resolve().parents[1]
VA = "2d3894048f5d61f6735955211bba28cb1e1a0ff9a7f556ebb6c144018388a865"
WEB = "b3ee38ecf4e26764c6ce19c1f0593839ed75aabcd37acb91daa7f8f0af155bce"
PACKAGE = "a877c0ef81fbbb4d42bee6c1de063fff47d610a5397ffc6ce7617f28269bfe73"
REFERENCE = "d73962c0592ae107d343591bf2d72e013015813e3b2ceff71d37e2c5fee36cd1"
ANNEXB = "12858642f02b0e1d98ddf409dd729a879b6a7a5d3434c860882532ca4f6b40af"
FFMPEG = "c8173e9755795978bce8e104f8d7044fabe7d6d84044aba37d3648c6f4e4e1a8"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def static_dependencies(p):
    refs = load(p / "targeted-reference-downloads.json")
    require(refs["commit"] == "3250ca07ca49e3f8c743066381b5688028681de8", "support commit")
    for row in refs["records"]:
        data = (p / row["path"]).read_bytes()
        blob = b"blob " + str(len(data)).encode() + b"\0" + data
        require(len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["SHA256"]
                and hashlib.sha1(blob).hexdigest() == row["Git_blob_SHA1"], "reference blob")
        require(not row["loaded"] and not row["execute_permission_added"], "static reference scope")
    web = p / "official/GeForceVADriverWeb.original"
    require(sha(web) == WEB and web.stat().st_size == 51520, "official WebVA")
    require(sha(p / "official/WebDriver-387.10.10.10.40.140.pkg") == PACKAGE, "NVIDIA package")
    for label, digest in [("installed", VA), ("official-web", WEB)]:
        path = (Path("/System/Library/Extensions/GeForceVADriver.bundle/Contents/MacOS/GeForceVADriver")
                if label == "installed" else web)
        require(sha(path) == digest, "VA identity")
        text = (p / (label + "-disassembly.txt")).read_text()
        chunks = re.findall(r"^\s*[0-9a-f]+:\s*((?:[0-9a-f]{2} )*[0-9a-f]{2})\s", text, re.M)
        code = bytes.fromhex(" ".join(chunks))
        # Store a digest, never redistribute the inspected vendor instruction bytes.
        require(len(code) == 22 and hashlib.sha256(code).hexdigest() ==
                "177905d91dfe9098122f671335e79fdfe394f5bad3e03c99eb8c6c3ad588d2fb"
                and code in path.read_bytes(), "two bounded constant-return bodies")
        require(text.count("_AVD_CreateAVDAccelerator:") == 1
                and text.count("_AVD_DestroyAVDAccelerator:") == 1, "factory labels")
    require("Section __text: 22" in (p / "official-web-sections.txt").read_text(), "WebVA text extent")
    web_row = next(r for r in refs["records"] if r["path"].endswith("/GeForceVADriverWeb"))
    native_row = next(r for r in refs["records"] if r["path"].endswith("/GeForceVADriver"))
    require(sha(p / web_row["path"]) == WEB and sha(p / native_row["path"]) == VA, "support/original identity")
    return {"support_commit": refs["commit"], "support_blobs_verified": len(refs["records"]),
            "NVIDIA_package_SHA256": PACKAGE, "WebVA_SHA256": WEB, "installed_VA_SHA256": VA,
            "official_WebVA_equals_support": True, "installed_VA_equals_native_support": True,
            "factory_text_bytes_per_binary": 22, "constant_return_per_factory": 14,
            "private_return_code_mapped_to_public_error": False,
            "factory_causally_responsible_for_VT_failure_proved": False,
            "installer_executed": False}


def independent_reference(p, build):
    fixture = build / "assets/fixture"
    f = load(fixture / "fixture.json")
    require(f["NAL_length_bytes"] == 4 and len(f["frames"]) == 6, "fixture geometry")
    start = b"\0\0\0\1"
    annexb = b"".join(start + base64.b64decode(x, validate=True) for x in f["H264_parameter_sets_base64"])
    for row in f["frames"]:
        data = (fixture / row["file"]).read_bytes()
        require(len(data) == row["bytes"], "compressed frame length")
        offset = 0
        while offset < len(data):
            require(offset + 4 <= len(data), "NAL prefix")
            n = int.from_bytes(data[offset:offset+4], "big")
            offset += 4
            require(n > 0 and offset + n <= len(data), "NAL payload extent")
            annexb += start + data[offset:offset+n]
            offset += n
    require(hashlib.sha256(annexb).hexdigest() == ANNEXB, "payload-preserving conversion")
    cpu = p / "cpu-reference"
    remote = cpu / "M1-result"
    require((cpu / "fixture-annexb.h264").read_bytes() == annexb
            == (remote / "fixture-annexb.h264").read_bytes(), "both-end compressed bytes")
    s, t = load(remote / "run-start.json"), load(remote / "run-terminal.json")
    inventory = load(p / "M1-FFmpeg-inventory.json")
    require(inventory["architecture"] == s["architecture"] == "arm64"
            and inventory["stdout"].startswith("ffmpeg version 9.0.2 "), "reference implementation")
    require(s["argv"] == t["argv"] and s["pid"] == t["pid"]
            and s["binary_SHA256"] == t["binary_SHA256_after"] == inventory["binary_SHA256"] == FFMPEG
            and s["input_SHA256"] == t["input_SHA256_after"] == ANNEXB, "M1 provenance")
    argv = s["argv"]
    require(argv[argv.index("-hwaccel")+1] == "none" and argv[argv.index("-c:v")+1] == "h264"
            and argv[argv.index("-frames:v")+1] == "6" and s["hardware_acceleration"] == "none",
            "software decoder command")
    require(t["exit_code"] == 0 and not t["SIGKILL_requested"] and not t["authoritative_ps_status"],
            "M1 process terminal")
    for name in ["stdout", "stderr"]:
        require(sha(remote / (name + ".txt")) == t[name + "_SHA256"], "M1 log transfer")
    require("h264 (native) -> rawvideo (native)" in (remote / "stderr.txt").read_text(), "decoder selection log")
    data = (remote / "decoded.nv12").read_bytes()
    require(len(data) == t["output_bytes"] == 691200 and sha(remote / "decoded.nv12")
            == t["output_SHA256"] == REFERENCE, "M1 frame transfer")
    require(load(p / "M1-result-transfer.json")["exit_code"] == 0, "result transfer status")
    return data


def cohort(root, build, lab, mode):
    inputs = terminal(root, lab, build)
    require(inputs == load(build / "inputs.json"), "execution/build pin")
    observation = load(root / "observation.json")
    require(observation == load(root / "outputs/observer.json"), "observer output provenance")
    o = observation["observer"]
    require(sha(build / "libVideoVAObserver.dylib") == inputs["observer_library_SHA256"]
            == observation["observer_library_SHA256"], "observer library")
    legacy = inputs["observer_library_SHA256"] in {
        "21027c59e7be2efe8f46513714d78d1df8c8c1ee2285dbd608219ef7d3ab98bd",
        "d2f5ce7b8aebf91581953db8a70c9ba6596d65d6c0993a284ca6d3ceefde3478"}
    if legacy:
        require("disabled_before_snapshot" not in o, "legacy snapshot schema")
    else:
        require(inputs["observer_library_SHA256"] ==
                "b378c3bdaede22a9a53eb1a42a45036170c544fc55a66232049821b5fcd97668"
                and o["disabled_before_snapshot"], "final disabled-snapshot observer")
    require(observation["mode"] == mode
            and not o["dropped"] and not o.get("IOKit_dropped", 0)
            and not o["native_instructions_modified"] and not o["arguments_modified"]
            and not o["direct_unknown_vendor_call"], "observer contract")
    require(not observation["system_modified"] and not observation["performance_benchmark"], "bounded observation")
    m = load(root / "execution/manifest.json")
    require(m["arguments"][-1] == mode, "actual process mode")
    result = load(root / "results.json")
    return result, o, m


def audit(lab):
    p = lab / "results/video-transport-progress-20261016"
    dep = static_dependencies(p)
    original = lab / "results/video-va-observer-build-20261016-04"
    derived = lab / "results/video-va-observer-build-20261016-05"
    a, b, d = load(original / "inputs.json"), load(derived / "inputs.json"), load(derived / "derivation.json")
    require(d["kind"] == "ASSET_ONLY_DERIVATION" and not d["executable_rebuilt"]
            and not d["execution_results_reused"] and d["original_compressed_fixtures_preserved"], "asset-only derivation")
    require(sha(original / "inputs.json") == b["source_build_inputs_SHA256"] == d["source_build_inputs_SHA256"]
            and sha(derived / "derivation.json") == b["derivation_SHA256"], "derivation pin")
    for name in ["application", "libVideoVAObserver.dylib", "vda.o", "vt.o"]:
        require(sha(original / name) == sha(derived / name), "same immutable code/object")
    for name, digest in a["assets_SHA256"].items():
        require(sha(derived / "assets" / name) == digest, "original assets retained")
    reference = independent_reference(p, original)
    require(d["reference_SHA256"] == REFERENCE, "staged reference pin")
    rows, manifests, synthetic = [], [], 0
    for suffix in ["", "-03", "-04"]:
        build_suffix = "-02" if not suffix else suffix
        build = lab / ("results/video-va-observer-build-20261016" + build_suffix)
        modes = ["selftest", "plain", "observe"] + (["vt-cpu"] if suffix == "-04" else [])
        for mode in modes:
            root = lab / ("results/video-va-observer-" + mode + "-20261016" + suffix)
            result, o, m = cohort(root, build, lab, mode)
            manifests.append(m)
            if mode == "selftest":
                require(result["integer_ABI_cases"] == result["floating_ABI_cases"] == 128
                        and o["create_calls"] == o["destroy_calls"] == 128
                        and o["dlsym_calls_observed"] >= 2 and o["bundle_calls_observed"] >= 1, "positive ABI calibration")
                synthetic += 256
            elif mode == "vt-cpu":
                require(result["output_frames"] == result["missing_CPU_references"] == 6
                        and result["CPU_reference_bytes_compared"] == 0
                        and result["frame_files"] == [], "incomplete numerical control retained")
            else:
                require(result["api"] == "VDA" and result["create_status"] == -12473, "VDA failure retained")
                require(o["create_calls"] == o["destroy_calls"] == 0 and not o["events"], "no monitored vendor factory")
            rows.append({"cohort": root.name, "exit_code": m["exit_code"], "mode": mode,
                         "result_SHA256": sha(root / "results.json"), "manifest_SHA256": sha(root / "execution/manifest.json")})
    for mode in ["vt-cpu", "vt-plain", "vt-observe"]:
        root = lab / ("results/video-va-observer-" + mode + "-20261016-05")
        result, o, m = cohort(root, derived, lab, mode)
        manifests.append(m)
        require(d["original_library_dependency"] in m["dependency_listing"], "actual original observer dependency")
        require(result["fixture_samples"] == 6 and result["format_create_status"] == 0, "valid VT fixture")
        if mode == "vt-cpu":
            decode = result["decode"]
            require(result["output_frames"] == 6 and result["CPU_reference_bytes_compared"] == 691200
                    and result["different_bytes"] == result["missing_CPU_references"] == 0, "independent CPU comparison")
            require(decode["create_status"] == decode["finish_status"] == decode["wait_status"] == 0
                    and decode["decode_status"] == [0]*6 and not decode["callback_errors"]
                    and decode["specification"] == {"EnableHardwareAcceleratedVideoDecoder": False}, "software-only VT command")
            require(decode["using_hardware"] == {"status": -12900, "value": None}, "unsupported property not false")
            pixels = b""
            for i in range(6):
                name = f"vt-frame-{i:03d}.nv12"
                frame = (root / "outputs" / name).read_bytes()
                require(len(frame) == 115200 and frame == reference[i*115200:(i+1)*115200]
                        == (root / "assets/fixture" / f"cpu-frame-{i:03d}.nv12").read_bytes(), "actual software pixels")
                pixels += frame
            require(pixels == reference, "frame ordering and reference")
        else:
            require(result["decode"]["create_status"] == -12906 and result["output_frames"] == 0
                    and result["CPU_reference_bytes_compared"] == 0 and not result["frame_files"]
                    and result["decode"]["specification"] == {"RequireHardwareAcceleratedVideoDecoder": True}, "hardware-only failure")
            require(o["create_calls"] == o["destroy_calls"] == 0 and not o["events"], "bounded lookup observation")
            if mode == "vt-observe":
                events = o["IOKit_events"]
                require(len(events) == 6 and all(len(x["stack"]) <= 12 for x in events), "bounded IOKit trace")
                require([(x["type_or_selector"], x["status"]) for x in events]
                        == [(0,0),(13,0),(44,3758097136),(5,0),(32,0),(6,0)], "actual trace sequence")
                require(any(Path(s["image"]).name == "MetalOld.dylib" for x in events for s in x["stack"]), "Metal initialization evidence")
        rows.append({"cohort": root.name, "exit_code": m["exit_code"], "mode": mode,
                     "result_SHA256": sha(root / "results.json"), "manifest_SHA256": sha(root / "execution/manifest.json")})
    ordered = sorted(manifests, key=lambda m: m["started_at"])
    for before, after in zip(ordered, ordered[1:]):
        require(datetime.datetime.fromisoformat(before["completed_at"]) <=
                datetime.datetime.fromisoformat(after["started_at"]), "overlapping native cohorts")
    start = load(p / "start.json")
    for row in start["system_before"]:
        require(sha(row["path"]) == row["SHA256"], "system file changed")
    require(len(start["system_before"]) == 83, "system inventory count")
    require(sha("/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist") == start["OCLP_SHA256"], "OCLP changed")
    image = start["existing_support_image"]
    require(sha(image["path"]) == image["SHA256"], "support image changed")
    common = load(lab / "results/native-allocation-runtime-build-20261016-04/manifest.json")
    for name, digest in common["source_SHA256"].items():
        require(sha(lab / name) == digest, "shared runtime source changed")
    require(len(common["source_SHA256"]) == 36, "runtime source count")
    require(sha(lab / "VIDEO.txt") == start["previous_video_report_SHA256"]
            and sha(lab / "results/video-summary.json") == start["previous_video_summary_SHA256"], "historical report changed")
    props = plistlib.loads((p / "current-nv-video-properties.stdout").read_bytes())
    require(len(props) == 1 and props[0]["IOVARendererID"] == bytes.fromhex("08000401")
            and props[0]["IOVARendererSubID"] == bytes.fromhex("03000000"), "native video renderer properties")
    return {"status": "PASS", "scope": "Evidence audit; hardware video remains unqualified",
            "dependencies": dep, "native_processes_terminal": len(rows), "synthetic_ABI_cases": synthetic,
            "legacy_VDA_failed_creates": 6, "VT_hardware_failed_creates": 2,
            "incomplete_first_CPU_control_retained": True, "asset_only_derivation_verified": True,
            "independent_CPU_reference": {"decoder": "FFmpeg 9.0.2 native H264, arm64, -hwaccel none",
                "binary_SHA256": FFMPEG, "annexb_SHA256": ANNEXB, "NV12_SHA256": REFERENCE,
                "iMac_software_VT_frames": 6, "active_bytes_compared": 691200, "different_bytes": 0,
                "using_hardware_property_unsupported_not_interpreted_as_false": True,
                "timestamp_conformance_tested": False},
            "VT_observed_IOKit_events": 6, "monitored_vendor_factory_calls": 0,
            "trace_proves_video_engine_submission": False, "nearest_symbol_is_exact_function_boundary": False,
            "video_renderer_properties_already_present": True, "cohorts_nonoverlapping": True,
            "unchanged_system_files": 83, "unchanged_runtime_sources": 36,
            "OCLP_unchanged": True, "support_image_unchanged": True,
            "cohorts": rows, "hardware_video_execution_proved": False,
            "performance_benchmark": "NOT RUN", "new_M1_Metal_GPU_reference": "NOT RUN",
            "installed_driver_modernized": False, "full_objective_complete": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.lab_root.resolve())
    with args.out.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps({k: result[k] for k in ["status", "native_processes_terminal", "synthetic_ABI_cases",
                     "hardware_video_execution_proved", "full_objective_complete"]}))


if __name__ == "__main__":
    main()
