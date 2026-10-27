#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and inspect a combined typed indexed/vertex shader without dispatch."""
from pathlib import Path
import argparse
import hashlib
import shutil
from public_large_scratch import ROOT,commands,preflight,sha,write
from metallib_air import extract
from lower_air_render_reset import normalized
from air_combined_index_vertex_lowering import lower
from verify_air_combined_inspection import PROFILE
import public_air_reset_dataflow as transport

AIR_SHA256='13cddbe0952a46a4123a2031efc1d0caf4288688bb2f8f12d65bcef05c2926ae'
IR_SHA256='a40a976cf50a8d7c696eb94493f81f95f4034e456ef307870f10b553107c0509'


def build(a):
    out=a.out.resolve();preflight(out);out.mkdir()
    for name in ['src','assets','runtime','oracles']:(out/name).mkdir()
    for name in ['air_reset_dataflow_probe.mm','NativeCommandBoundaryCapture.inc','public_air_combined_index_vertex.py',
      'air_combined_index_vertex_lowering.py','air_vertex_binding_lowering.py','air_indexed_render_lowering.py',
      'air_render_draw_lowering.py','air_reset_lowering.py','lower_air_render_reset.py','metallib_air.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    for name in ['KeplerGPUIdentity.h','air_combined_index_vertex.metal']:shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['verify_air_combined_inspection.py','verify_air_reset_dataflow.py','verify_air_render_reset.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    run=commands(out)
    run('original-metal',['xcrun','metal','-std=macos-metal2.3','-fmodules=none','-c',out/'src/air_combined_index_vertex.metal','-o',out/'original.air'])
    run('original-metallib',['xcrun','metallib',out/'original.air','-o',out/'assets/original.metallib'])
    module=extract((out/'assets/original.metallib').read_bytes(),'probe_boundary');assert module['sha256']==AIR_SHA256,'Unknown AIR profile'
    (out/'original-extracted.air').write_bytes(module['wrapped_AIR'])
    run('original-IR',['xcrun','metal','-S','-emit-llvm','-x','ir',out/'original-extracted.air','-o',out/'original.ll'])
    ir=(out/'original.ll').read_text();assert hashlib.sha256(normalized(ir).encode()).hexdigest()==IR_SHA256,'Unknown normalized IR'
    (out/'assets/lowered.ll.txt').write_text(lower(ir))
    run('lowered-air',['xcrun','metal','-x','ir','-O2','-c',out/'assets/lowered.ll.txt','-o',out/'lowered.air'])
    run('lowered-metallib',['xcrun','metallib',out/'lowered.air','-o',out/'assets/lowered.metallib'])
    run('lowered-IR',['xcrun','metal','-S','-emit-llvm','-x','ir',out/'lowered.air','-o',out/'assets/optimized.ll.txt'])
    opt=(out/'assets/optimized.ll.txt').read_text()
    for name in ['@air.set_vertex_buffer','@air.draw_indexed','@air.reset_render_command','@kp_set_vertex_buffer','@kp_indexed_render_','@kp_reset_render_command']:assert name not in opt,name
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-DKP_AIR_INSPECTION_ONLY=1','-I',out/'src',out/'src/air_reset_dataflow_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
    write(out/'inputs.json',dict(profile=PROFILE,original_AIR_SHA256=module['sha256'],frozen={str(p.relative_to(out)):sha(p)for folder in ['src','runtime','oracles','assets']for p in(out/folder).iterdir()if p.is_file()},executable_SHA256=sha(out/'application'),core_runtime_linked=False,inspection_only_host=True))


def inspect(a):
    a.mode='inspect';a.certificate=None;a.variant='lowered';transport.run(a,oracle_module='verify_air_combined_inspection')
def certify(a):transport.certify(a,oracle_module='verify_air_combined_inspection',profile=PROFILE)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(required=True)
    b=sub.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
    r=sub.add_parser('inspect')
    for name in ['build','out','reservation-root']:r.add_argument('--'+name,type=Path,required=True)
    r.set_defaults(func=inspect)
    c=sub.add_parser('certify');c.add_argument('--run',type=Path,required=True);c.add_argument('--envydis',type=Path,required=True);c.set_defaults(func=certify)
    a=p.parse_args();a.func(a)
