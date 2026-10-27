#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline vertex-setter lowering and construction-only native inspection.

No command dispatch is available. The extension has no owned host context or
resource-lifetime implementation; compilation/inspection is not execution.
"""
from pathlib import Path
import argparse
import hashlib
import shutil
from public_large_scratch import ROOT, commands, preflight, sha, write
from metallib_air import extract
from lower_air_render_reset import normalized
from air_vertex_binding_lowering import lower
from verify_air_vertex_binding_inspection import PROFILE
import public_air_reset_dataflow as transport

AIR_SHA256 = 'b8e67ce59ef9abeb0f75fe3871cfbe0968fbe36fe3515c7bbcad2c0d78a96380'
IR_SHA256 = '1c7b8f1e1e1847f093b258adb83fdfe25bb86293b92fbac7334bef9be59e9ce0'


def build(a):
    out = a.out.resolve()
    preflight(out)
    out.mkdir()
    for name in ['src', 'assets', 'runtime', 'oracles']:
        (out / name).mkdir()
    for name in ['air_reset_dataflow_probe.mm', 'NativeCommandBoundaryCapture.inc',
                 'public_air_vertex_binding.py', 'air_vertex_binding_lowering.py',
                 'air_render_draw_lowering.py', 'air_reset_lowering.py', 'lower_air_render_reset.py', 'metallib_air.py']:
        shutil.copyfile(ROOT / 'tools' / name, out / 'src' / name)
    for name in ['KeplerGPUIdentity.h', 'air_vertex_binding.metal']:
        shutil.copyfile(ROOT / 'src' / name, out / 'src' / name)
    for name in ['verify_air_vertex_binding_inspection.py', 'verify_air_reset_dataflow.py',
                 'verify_air_render_reset.py', 'verify_local_memory.py', 'public_large_scratch.py']:
        shutil.copyfile(ROOT / 'tools' / name, out / 'oracles' / name)
    shutil.copyfile(ROOT / 'tools/lab_gpu_reservation.py', out / 'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT / 'sdk-combined/runtime/run_sdk_host.py', out / 'runtime/run_sdk_host.py')
    run = commands(out)
    run('original-metal', ['xcrun', 'metal', '-std=macos-metal2.3', '-fmodules=none', '-c', out/'src/air_vertex_binding.metal', '-o', out/'original.air'])
    run('original-metallib', ['xcrun', 'metallib', out/'original.air', '-o', out/'assets/original.metallib'])
    module = extract((out/'assets/original.metallib').read_bytes(), 'probe_boundary')
    assert module['sha256'] == AIR_SHA256, 'Unknown AIR profile'
    (out/'original-extracted.air').write_bytes(module['wrapped_AIR'])
    run('original-IR', ['xcrun', 'metal', '-S', '-emit-llvm', '-x', 'ir', out/'original-extracted.air', '-o', out/'original.ll'])
    ir = (out/'original.ll').read_text()
    assert hashlib.sha256(normalized(ir).encode()).hexdigest() == IR_SHA256, 'Unknown normalized IR'
    (out/'assets/lowered.ll.txt').write_text(lower(ir))
    run('lowered-air', ['xcrun', 'metal', '-x', 'ir', '-O2', '-c', out/'assets/lowered.ll.txt', '-o', out/'lowered.air'])
    run('lowered-metallib', ['xcrun', 'metallib', out/'lowered.air', '-o', out/'assets/lowered.metallib'])
    run('lowered-IR', ['xcrun', 'metal', '-S', '-emit-llvm', '-x', 'ir', out/'lowered.air', '-o', out/'assets/optimized.ll.txt'])
    optimized = (out/'assets/optimized.ll.txt').read_text()
    assert '@air.set_vertex_buffer' not in optimized and '@air.draw_primitives' not in optimized
    assert '@kp_set_vertex_buffer' not in optimized and '@kp_draw_primitives' not in optimized
    run('host', ['xcrun', 'clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc', '-DKP_AIR_INSPECTION_ONLY=1', '-I', out/'src', out/'src/air_reset_dataflow_probe.mm', '-framework', 'Metal', '-framework', 'Foundation', '-o', out/'application'])
    write(out/'inputs.json', dict(profile=PROFILE, original_AIR_SHA256=module['sha256'],
        frozen={str(p.relative_to(out)):sha(p) for folder in ['src', 'runtime', 'oracles', 'assets'] for p in (out/folder).iterdir() if p.is_file()},
        executable_SHA256=sha(out/'application'), core_runtime_linked=False, inspection_only_host=True))


def inspect(a):
    a.mode = 'inspect'
    a.certificate = None
    a.variant = 'lowered'
    transport.run(a, oracle_module='verify_air_vertex_binding_inspection')


def certify(a):
    transport.certify(a, oracle_module='verify_air_vertex_binding_inspection', profile=PROFILE)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(required=True)
    b = subs.add_parser('build')
    b.add_argument('--out', type=Path, required=True)
    b.set_defaults(func=build)
    r = subs.add_parser('inspect')
    for name in ['build', 'out', 'reservation-root']:
        r.add_argument('--' + name, type=Path, required=True)
    r.set_defaults(func=inspect)
    c = subs.add_parser('certify')
    c.add_argument('--run', type=Path, required=True)
    c.add_argument('--envydis', type=Path, required=True)
    c.set_defaults(func=certify)
    a = p.parse_args()
    a.func(a)
