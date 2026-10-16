#!/usr/bin/env python3
"""Build bounded sequential segments of nested native control, without GPU work.

Function suffixes denote total source levels, not simultaneous nesting. The
original runtime and native program remain unchanged by the experimental
reservation factory. This builder never launches the resulting executable.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SEGMENTS = {96: [48, 48], 120: [65, 55]}
MASK = (1 << 32) - 1
EXPERIMENT = "ecff9c4f83d25283cf35a31ac77f53bcc9d1032a77b21209aba07ce3c5795991"
DRIVER = "2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configuration():
    return {"schema": 1, "variant": "segmented", "depths": list(SEGMENTS),
            "segments": {"depth" + str(n): pieces for n, pieces in SEGMENTS.items()},
            "level_numbering": "global across consecutive segments",
            "maximum_loop_body_visits_per_thread": 240,
            "function_suffix_is_total_levels_not_maximum_nesting": True}


def source():
    lines = ["// SPDX-License-Identifier: MIT", "#include <metal_stdlib>", "using namespace metal;",
             "struct Params {uint seed,count,stride,reserved;};",
             "static uint rol5(uint x){return (x<<5)|(x>>27);}"]
    for total, pieces in SEGMENTS.items():
        assert sum(pieces) == total <= 120 and all(0 < n <= 65 for n in pieces)
        lines += [f"kernel void depth{total}(volatile device const uint*input [[buffer(0)]],",
                  "device uint4*output [[buffer(1)]],constant Params&p [[buffer(2)]],uint gid [[thread_position_in_grid]]){",
                  "if(gid>=p.count)return;uint base=gid*p.stride;",
                  "uint state=input[base]+p.seed+gid*747796405u,visits=0;"]
        begin = 0
        for length in pieces:
            end = begin + length
            lines.append("{")
            for level in range(begin, end):
                lines += [f"uint limit{level}=1u+((input[base+{level+1}]^p.seed^p.reserved)&1u);",
                          "#pragma clang loop unroll(disable)",
                          f"for(uint iter{level}=0;iter{level}<limit{level};++iter{level}){{",
                          f"state=rol5(state^input[base+{level+1}])+({level}u*2891336453u+iter{level});"]
                if level + 1 < end:
                    lines.append(f"if(iter{level}==0){{")
            for level in reversed(range(begin, end)):
                if level + 1 < end:
                    lines.append("}")
                lines += [f"state=(state*1664525u+1013904223u)^({level}u*97u+iter{level}+p.reserved);",
                          "visits++;", "}"]
            lines.append("}")
            begin = end
        lines += ["output[gid]=uint4(rol5(state)^p.seed,state,visits,0xcafe0000u^gid);", "}"]
    return "\n".join(lines) + "\n"


def rotate(x):
    return ((x << 5) | (x >> 27)) & MASK


def result_for_segments(pieces, gid, seed, reserved):
    value = lambda i: ((((gid * 129 + i) * 1664525 + 1013904223) & MASK) ^ seed)
    state = (value(0) + seed + gid * 747796405) & MASK
    visits = 0

    def walk(level, end, state):
        count = 0
        for turn in range(1 + ((value(level + 1) ^ seed ^ reserved) & 1)):
            state = (rotate(state ^ value(level + 1)) + level * 2891336453 + turn) & MASK
            if turn == 0 and level + 1 < end:
                state, child = walk(level + 1, end, state)
                count += child
            state = (((state * 1664525 + 1013904223) & MASK)
                     ^ (level * 97 + turn + reserved)) & MASK
            count += 1
        return state, count

    begin = 0
    for length in pieces:
        assert length > 0 and begin + length <= 120
        state, count = walk(begin, begin + length, state)
        visits += count
        begin += length
    assert begin <= visits <= 2 * begin
    return rotate(state) ^ seed, state, visits, 0xcafe0000 ^ gid


def iterative_result(pieces, gid, seed, reserved):
    """Separate event-stack implementation, also checked against old oracles."""
    value = lambda i: ((((gid * 129 + i) * 1664525 + 1013904223) & MASK) ^ seed)
    state = (value(0) + seed + gid * 747796405) & MASK
    visits = begin = 0
    for length in pieces:
        end = begin + length
        pending = [("expand", begin, 0)]
        while pending:
            kind, level, turn = pending.pop()
            if kind == "expand":
                limit = 1 + ((value(level + 1) ^ seed ^ reserved) & 1)
                for i in reversed(range(limit)):
                    pending.append(("after", level, i))
                    if i == 0 and level + 1 < end:
                        pending.append(("expand", level + 1, 0))
                    pending.append(("before", level, i))
            elif kind == "before":
                state = (rotate(state ^ value(level + 1)) + level * 2891336453 + turn) & MASK
            else:
                assert kind == "after"
                state = (((state * 1664525 + 1013904223) & MASK)
                         ^ (level * 97 + turn + reserved)) & MASK
                visits += 1
        begin = end
    assert begin <= visits <= 2 * begin
    return rotate(state) ^ seed, state, visits, 0xcafe0000 ^ gid


def result(total, gid, seed, reserved):
    return result_for_segments(SEGMENTS[total], gid, seed, reserved)


def run(out, commands, label, argv):
    argv = list(map(str, argv))
    start = time.monotonic()
    r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    (out / (label + ".stdout")).write_text(r.stdout)
    (out / (label + ".stderr")).write_text(r.stderr)
    commands.append({"label": label, "argv": argv, "exit_code": r.returncode,
                     "monotonic_seconds": time.monotonic() - start})
    (out / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
    assert r.returncode == 0, (label, r.stderr[-3000:])
    print(label, "PASS", flush=True)


def native(out):
    out.mkdir(exist_ok=False)
    (out / "assets").mkdir()
    (out / "runtime").mkdir()
    (out / "segmented_control.metal").write_text(source())
    (out / "assets/control_flow_config.json").write_text(json.dumps(configuration(), indent=2) + "\n")
    (out / "assets/segmented-control.json").write_text(json.dumps(configuration(), indent=2) + "\n")
    shutil.copyfile(__file__, out / "builder.py")
    shutil.copyfile(ROOT / "tools/compiler_output_trace.mm", out / "compiler_output_trace.mm")
    for name in ["run_sdk_host.py", "lab_gpu_reservation.py"]:
        src = ROOT / ("sdk-combined/runtime" if name == "run_sdk_host.py" else "tools") / name
        shutil.copyfile(src, out / "runtime" / name)
    commands = []
    run(out, commands, "metal", ["xcrun", "metal", "-std=macos-metal2.3", "-c",
                                  out / "segmented_control.metal", "-o", out / "segmented_control.air"])
    run(out, commands, "metallib", ["xcrun", "metallib", out / "segmented_control.air", "-o", out / "assets/control_flow.metallib"])
    run(out, commands, "capture", ["clang++", "-arch", "x86_64", "-O2", "-std=c++17", "-fno-objc-arc",
                                    out / "compiler_output_trace.mm", "-framework", "Metal", "-framework", "Foundation",
                                    "-o", out / "compiler_output_trace"])
    inputs = {"source_hashes": {n: sha(out / n) for n in ["builder.py", "segmented_control.metal", "compiler_output_trace.mm"]},
              "assets_SHA256": {p.name: sha(p) for p in (out / "assets").iterdir()},
              "runtime_SHA256": {p.name: sha(p) for p in (out / "runtime").iterdir()},
              "capture_executable_SHA256": sha(out / "compiler_output_trace"),
              "source_generator_SHA256": sha(out / "builder.py"), "depths": list(SEGMENTS),
              "variant": "segmented", "segments": configuration()["segments"], "entry_witness": False,
              "GPU_execution": False, "work_bound": "At most twice the total source levels, at most240loop body visits/thread"}
    (out / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")


def client(out, native_build, observations, library, reserve, backend):
    assert (backend == "common" and reserve == 4096) or (backend == "standalone" and reserve in [2048, 2560])
    ni = json.loads((native_build / "inputs.json").read_text())
    od = json.loads((observations / "observations.json").read_text())
    lm = json.loads((library / "manifest.json").read_text())
    assert od["native_build_inputs_SHA256"] == sha(native_build / "inputs.json") and od["driver_SHA256"] == DRIVER
    assert sha(library / "libKeplerMetal.a") == lm["static_library_SHA256"]
    assert ni["segments"] == configuration()["segments"] and ni["variant"] == "segmented"
    assert json.loads((observations / "status.json").read_text())["status"] == "PASS"
    for n, h in ni["source_hashes"].items():
        assert sha(native_build / n) == h
    for n, h in ni["assets_SHA256"].items():
        assert sha(native_build / "assets" / n) == h
    out.mkdir(exist_ok=False)
    shutil.copytree(native_build / "assets", out / "assets")
    shutil.copytree(native_build / "runtime", out / "runtime")
    manifest = {"library_sha256": sha(out / "assets/control_flow.metallib"), "certificates": {}}
    assert len(od["records"]) == 2
    for row in od["records"]:
        name, w = row["function"], row["metadata_words"]
        assert name in configuration()["segments"] and w[11] <= reserve <= 4096
        assert sha(observations / name / "capture/native.sass") == row["code_SHA256"]
        assert row["code_bytes"] <= 104000 and w[7] <= 63 and w[12] <= 4656
        assert w[9] == 64 * w[12] + w[11] and w[12] == w[13]
        cert = {"schema": 1, "intent": "native_control_reservation" if backend == "common" else "native_control_reservation_experiment",
                "function": name, "driver_sha256": DRIVER, "library_sha256": manifest["library_sha256"],
                "native_code_sha256": row["code_SHA256"], "code_bytes": row["code_bytes"],
                "metadata_words": w, "control_reserve": reserve}
        file = out / "assets" / ("allocation-" + name + ".json")
        file.write_text(json.dumps(cert, sort_keys=True, indent=2) + "\n")
        manifest["certificates"][name] = {"file": file.name, "SHA256": sha(file)}
    (out / "assets/native-allocation-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    names = ["native_allocation_qmd_execute.mm", "native_allocation_qmd_capture.mm", "KeplerNativeAllocation.h"]
    if backend == "standalone":
        names += ["native_segmented_reserve_probe.mm", "NativeControlReserveExperiment.mm"]
    for name in names:
        src = library / "src" / name if name.endswith(".h") else ROOT / "tools" / name
        shutil.copyfile(src, out / name)
    shutil.copyfile(__file__, out / "builder.py")
    names.append("builder.py")
    commands = []
    objects = []
    entry = "native_allocation_qmd_execute.mm"
    if backend == "standalone":
        assert sha(out / "NativeControlReserveExperiment.mm") == EXPERIMENT
        run(out, commands, "standalone", ["clang++", "-arch", "x86_64", "-O2", "-std=c++17", "-fno-objc-arc",
                                          "-c", out / "NativeControlReserveExperiment.mm", "-o", out / "standalone.o"])
        objects.append(out / "standalone.o")
        entry = "native_segmented_reserve_probe.mm"
    run(out, commands, "client", ["clang++", "-arch", "x86_64", "-O2", "-std=c++17", "-fobjc-arc", "-I", out,
                                   out / entry, *objects, library / "libKeplerMetal.a", "-Wl,-ObjC",
                                   "-framework", "Foundation", "-framework", "Metal", "-o", out / "application"])
    inputs = {"source_hashes": {n: sha(out / n) for n in names},
              "assets_SHA256": {p.name: sha(p) for p in (out / "assets").iterdir()},
              "runtime_SHA256": {p.name: sha(p) for p in (out / "runtime").iterdir()},
              "executable_SHA256": sha(out / "application"), "static_library_SHA256": sha(library / "libKeplerMetal.a"),
              "library_manifest_SHA256": sha(library / "manifest.json"), "source_generator_SHA256": sha(out / "builder.py"),
              "native_build_inputs_SHA256": sha(native_build / "inputs.json"),
              "observations_SHA256": sha(observations / "observations.json"),
              "allocation_backend": backend, "requested_reserve": reserve,
              "standalone_object_SHA256": sha(out / "standalone.o") if objects else None,
              "client_will_submit": True, "GPU_execution": False}
    (out / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="phase", required=True)
    a = sub.add_parser("native")
    a.add_argument("--lab-root", type=Path, help="Existing bridge tree and shared laboratory root")
    a.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("client")
    a.add_argument("--lab-root", type=Path, help="Existing bridge tree and shared laboratory root")
    for n in ["out", "native-build", "observations", "library"]:
        a.add_argument("--" + n, type=Path, required=True)
    a.add_argument("--backend", choices=["common", "standalone"], required=True)
    a.add_argument("--reserve", type=int, choices=[2048, 2560, 4096], required=True)
    args = parser.parse_args()
    if args.lab_root:
        ROOT = args.lab_root.resolve()
    out = args.out.resolve()
    out.relative_to(ROOT / "results")
    if args.phase == "native":
        native(out)
    else:
        client(out, args.native_build.resolve(), args.observations.resolve(), args.library.resolve(), args.reserve, args.backend)
    print(json.dumps({"status": "PASS", "phase": args.phase, "GPU_execution": False}))
