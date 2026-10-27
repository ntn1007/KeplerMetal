#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and serialize a signed, bounded pipeline-transition render probe."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
from public_large_scratch import ROOT, check_library, check_driver_profile, commands, preflight, read, sha, write
from verify_air_pipeline_binding_inspection import verify as verify_inspection
from verify_pipeline_binding_render import MODES, EXTRA_MODES


def build(a):
    out,lib,producer,inspection=a.out.resolve(),a.library.resolve(),a.producer.resolve(),a.inspection.resolve()
    preflight(out);manifest=check_library(lib)
    assert verify_inspection(inspection)['mode']=='inspect'
    cert=read(inspection/'certificate.json');pm=read(producer/'inputs.json')
    assert cert['no_native_call'] and cert['library_SHA256']==sha(producer/'assets/lowered.metallib')
    assert cert['inspection_inputs_SHA256']==sha(inspection/'inputs.json') and cert['inspection_results_SHA256']==sha(inspection/'results.json')
    for name,digest in pm['frozen'].items():assert sha(producer/name)==digest,name
    out.mkdir()
    for folder in ['src','assets','runtime','oracles','library-src']:(out/folder).mkdir()
    for name in manifest['source_SHA256']:shutil.copyfile(lib/'src'/name,out/'library-src'/name)
    for name in ['render_state_carrier.metal','vertex_io_carrier.metal','cpu_icb_vertex_profiles.json','render_state_catalogue.metal','KeplerRenderStateRecords.h','KeplerGPUIdentity.h','KeplerIndirectRenderRangePins.h']:
        shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['pipeline_binding_render_probe.mm','AIRCertifiedResetPipeline.h','AIRCertifiedResetPipeline.mm','NativeCommandBoundaryCapture.inc','OwnedKeplerComputeCode.inc']:
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    for name in ['verify_pipeline_binding_render.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    shutil.copyfile(producer/'assets/lowered.metallib',out/'assets/vertex.metallib')
    shutil.copyfile(inspection/'certificate.json',out/'assets/vertex.certificate.json')
    shutil.copyfile(out/'src/cpu_icb_vertex_profiles.json',out/'assets/vertex_profiles.json')
    run=commands(out)
    for source,name,flags in [('render_state_carrier','render_state_carrier',[]),('vertex_io_carrier','vertex_io_carrier',[]),('render_state_catalogue','state',['-fmodules=none','-I',out/'src'])]:
        run(name+'-metal',['xcrun','metal','-std=macos-metal2.4',*flags,'-c',out/'src'/(source+'.metal'),'-o',out/(name+'.air')])
        run(name+'-metallib',['xcrun','metallib',out/(name+'.air'),'-o',out/'assets'/(name+'.metallib')])
    assert sha(out/'assets/render_state_carrier.metallib')=='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
    assert sha(out/'assets/vertex_io_carrier.metallib')==read(out/'assets/vertex_profiles.json')['library_SHA256']
    assert sha(out/'assets/state.metallib') in (out/'src/KeplerIndirectRenderRangePins.h').read_text()
    run('capture-MRC',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out/'src','-c',out/'src/AIRCertifiedResetPipeline.mm','-o',out/'capture.o'])
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src','-I',out/'library-src',out/'src/pipeline_binding_render_probe.mm',out/'capture.o',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])
    frozen={str(p.relative_to(out)):sha(p) for folder in ['src','assets','runtime','oracles','library-src'] for p in (out/folder).iterdir() if p.is_file()}
    write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':sha(out/'application'),'static_library_SHA256':manifest['static_library_SHA256'],'GPU_execution':False})


def run(a):
    build,out=a.build.resolve(),a.out.resolve();data=read(build/'inputs.json');assert not out.exists() and out.parent.is_dir()
    for name,digest in data['frozen'].items():assert sha(build/name)==digest,name
    assert sha(build/'application')==data['executable_SHA256'];driver=check_driver_profile();cert=read(build/'assets/vertex.certificate.json');assert cert['driver_SHA256']==driver
    out.mkdir();(out/'outputs').mkdir()
    for folder in ['src','assets','runtime','oracles','library-src']:shutil.copytree(build/folder,out/folder)
    shutil.copyfile(build/'application',out/'application');(out/'application').chmod(0o755)
    write(out/'inputs.json',dict(data,mode=a.mode,driver_SHA256=driver,source_build_inputs_SHA256=sha(build/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    result=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'outputs'),a.mode],a.reservation_root.resolve())
    write(out/'results.json',read(out/'execution/execution.stdout'))
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_pipeline_binding_render import verify;print(json.dumps(verify(sys.argv[2])))'
    p=subprocess.run([sys.executable,'-I','-c',code,str(out/'oracles'),str(out)],capture_output=True,text=True)
    (out/'verification.stdout').write_text(p.stdout);(out/'verification.stderr').write_text(p.stderr)
    write(out/'verification-execution.json',{'exit_code':p.returncode,'isolated_interpreter':True})
    if p.returncode:raise RuntimeError('Independent oracle failed; inspect terminal host: '+str(out/'verification.stderr'))
    proof=json.loads(p.stdout);write(out/'independent-verification.json',dict(proof,PID=result['pid']));print(proof)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(required=True)
    b=sub.add_parser('build')
    for k in ['library','producer','inspection','out']:b.add_argument('--'+k,type=Path,required=True)
    b.set_defaults(func=build)
    r=sub.add_parser('run')
    for k in ['build','out','reservation-root']:r.add_argument('--'+k,type=Path,required=True)
    r.add_argument('--mode',choices=MODES+EXTRA_MODES,required=True);r.set_defaults(func=run)
    args=p.parse_args();args.func(args)
