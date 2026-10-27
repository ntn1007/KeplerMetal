#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build typed indexed programs and inspect/certify them without dispatch."""
from pathlib import Path
import argparse
import hashlib
import shutil
from public_large_scratch import ROOT,commands,preflight,sha,write
from metallib_air import extract
from lower_air_render_reset import normalized
from air_indexed_render_lowering import lower
from verify_air_indexed_inspection import PROFILE
import public_air_reset_dataflow as transport

AIR_SHA256='fe2f89f4f01a791babd17415e12ad4ad43ec172c8536dc1c5c50408a093273af'
IR_SHA256='5483170015aa7e576a88bea00b71013068b554ae1d2bcf90a5f772999cb98109'


def build(a):
    out=a.out.resolve();preflight(out);out.mkdir()
    for name in ['src','assets','runtime','oracles']:(out/name).mkdir()
    for name in ['air_reset_dataflow_probe.mm','NativeCommandBoundaryCapture.inc','public_air_indexed_render.py',
        'public_air_reset_dataflow.py','air_indexed_render_lowering.py','air_reset_lowering.py','lower_air_render_reset.py','metallib_air.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    for name in ['KeplerGPUIdentity.h','KeplerIndexedRenderRecords.h','air_indexed_render.metal','air_indexed_render_reference.metal']:
        shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['verify_air_indexed_inspection.py','verify_air_reset_dataflow.py','verify_air_render_reset.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    run=commands(out)
    run('original-metal',['xcrun','metal','-std=macos-metal2.3','-fmodules=none','-c',out/'src/air_indexed_render.metal','-o',out/'original.air'])
    run('original-metallib',['xcrun','metallib',out/'original.air','-o',out/'assets/original.metallib'])
    module=extract((out/'assets/original.metallib').read_bytes(),'probe_boundary');assert module['sha256']==AIR_SHA256,'Unknown indexed AIR profile'
    (out/'original-extracted.air').write_bytes(module['wrapped_AIR'])
    run('original-IR',['xcrun','metal','-S','-emit-llvm','-x','ir',out/'original-extracted.air','-o',out/'original.ll'])
    ir=(out/'original.ll').read_text();assert hashlib.sha256(normalized(ir).encode()).hexdigest()==IR_SHA256
    (out/'assets/lowered.ll.txt').write_text(lower(ir))
    run('lowered-air',['xcrun','metal','-x','ir','-O2','-c',out/'assets/lowered.ll.txt','-o',out/'lowered.air'])
    run('lowered-metallib',['xcrun','metallib',out/'lowered.air','-o',out/'assets/lowered.metallib'])
    run('lowered-IR',['xcrun','metal','-S','-emit-llvm','-x','ir',out/'lowered.air','-o',out/'assets/optimized.ll.txt'])
    optimized=(out/'assets/optimized.ll.txt').read_text()
    assert '@air.draw_indexed'not in optimized and '@air.reset_render_command'not in optimized
    assert '@kp_indexed_render_'not in optimized and '@kp_reset_render_command'not in optimized
    run('reference-air',['xcrun','metal','-std=macos-metal2.3','-fmodules=none','-I',out/'src','-c',out/'src/air_indexed_render_reference.metal','-o',out/'reference.air'])
    run('reference-metallib',['xcrun','metallib',out/'reference.air','-o',out/'assets/reference.metallib'])
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-DKP_AIR_INSPECTION_ONLY=1','-I',out/'src',out/'src/air_reset_dataflow_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
    write(out/'inputs.json',dict(profile=PROFILE,original_AIR_SHA256=module['sha256'],
        frozen={str(p.relative_to(out)):sha(p)for folder in ['src','runtime','oracles','assets']for p in(out/folder).iterdir()if p.is_file()},
        executable_SHA256=sha(out/'application'),core_runtime_linked=False,inspection_only_host=True))


def inspect(a):
    a.mode='inspect';a.certificate=None;transport.run(a,oracle_module='verify_air_indexed_inspection')
def certify(a):transport.certify(a,oracle_module='verify_air_indexed_inspection',profile=PROFILE)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
    r=s.add_parser('inspect')
    for name in ['build','out','reservation-root']:r.add_argument('--'+name,type=Path,required=True)
    r.add_argument('--variant',choices=['lowered','reference'],required=True);r.set_defaults(func=inspect)
    c=s.add_parser('certify');c.add_argument('--run',type=Path,required=True);c.add_argument('--envydis',type=Path,required=True);c.set_defaults(func=certify)
    a=p.parse_args();a.func(a)
