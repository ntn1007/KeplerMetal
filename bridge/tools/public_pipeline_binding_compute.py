#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and run a certified, bounded compute-only pipeline-binding probe."""
from pathlib import Path
import argparse
import shutil
import subprocess
import sys
from public_large_scratch import ROOT, commands, preflight, read, sha, write
import public_air_reset_dataflow as transport

PROFILE = 'typed-pipeline-binding-air28-experiment-v1'
MODES = ('active', 'wrong_token', 'foreign_source', 'wrong_slot', 'row_reserved',
         'bad_extension', 'bad_header', 'no_dispatch')


def build(a):
    inspection = a.inspection.resolve(); out = a.out.resolve()
    code = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
            'from verify_air_pipeline_binding_inspection import verify;print(json.dumps(verify(sys.argv[2])))')
    subprocess.run([sys.executable, '-I', '-c', code, str(inspection/'oracles'), str(inspection)], check=True, capture_output=True, text=True)
    certificate = read(inspection/'certificate.json')
    assert certificate['profile'] == PROFILE and certificate['no_native_call'] is True
    assert certificate['library_SHA256'] == sha(inspection/'assets/lowered.metallib')
    assert certificate['inspection_inputs_SHA256'] == sha(inspection/'inputs.json')
    assert certificate['inspection_results_SHA256'] == sha(inspection/'results.json')
    preflight(out);out.mkdir()
    for folder in ('src','assets','runtime','oracles'): (out/folder).mkdir()
    for name in ('pipeline_binding_compute_probe.mm','NativeCommandBoundaryCapture.inc','public_pipeline_binding_compute.py'):
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    shutil.copyfile(ROOT/'src/KeplerGPUIdentity.h',out/'src/KeplerGPUIdentity.h')
    shutil.copyfile(inspection/'assets/lowered.metallib',out/'assets/lowered.metallib')
    for name in ('verify_pipeline_binding_compute.py','verify_air_render_reset.py','verify_local_memory.py','public_large_scratch.py'):
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    commands(out)('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc',
                        '-I',out/'src',out/'src/pipeline_binding_compute_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
    frozen={str(p.relative_to(out)):sha(p) for group in ('src','assets','runtime','oracles') for p in (out/group).iterdir() if p.is_file()}
    write(out/'inputs.json',{'profile':PROFILE,'frozen':frozen,'executable_SHA256':sha(out/'application'),
                             'core_runtime_linked':False,'inspection_certificate_SHA256':sha(inspection/'certificate.json')})


def run(a):
    assert sha(a.certificate.resolve()) == read(a.build.resolve()/'inputs.json')['inspection_certificate_SHA256']
    a.variant = 'lowered'
    transport.run(a,oracle_module='verify_pipeline_binding_compute')


if __name__ == '__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--inspection',type=Path,required=True);b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
    r=s.add_parser('run')
    for name in ('build','out','reservation-root','certificate'):r.add_argument('--'+name,type=Path,required=True)
    r.add_argument('--mode',choices=MODES,required=True);r.set_defaults(func=run)
    a=p.parse_args();a.func(a)
