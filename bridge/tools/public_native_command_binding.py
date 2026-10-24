#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read owned native code; encode suspect work but submit only optional blits."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from public_large_scratch import ROOT,commands,preflight,read,sha,write,check_driver_profile
from public_native_command_boundary import CASES,source
CASES=tuple(c for c in CASES if not c.startswith('typed_'))
MODES=('inspect','encode','readback','readback_no_copy')


def build(a):
    out=a.out.resolve();preflight(out);out.mkdir()
    for folder in ['src','assets','runtime','oracles']:(out/folder).mkdir()
    for name in ['native_command_binding_probe.mm','NativeCommandBoundaryCapture.inc','public_native_command_binding.py','public_native_command_boundary.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    shutil.copyfile(ROOT/'src/KeplerGPUIdentity.h',out/'src/KeplerGPUIdentity.h')
    for name in ['verify_native_command_binding.py','verify_native_command_boundary.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    run=commands(out)
    for case in CASES:
        shader=out/'src'/(case+'.metal');shader.write_text('// SPDX-License-Identifier: MIT\n'+source(case))
        run(case+'-metal',['xcrun','metal','-std=macos-metal2.3','-fmodules=none','-c',shader,'-o',out/(case+'.air')])
        run(case+'-metallib',['xcrun','metallib',out/(case+'.air'),'-o',out/'assets'/(case+'.metallib')])
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out/'src',out/'src/native_command_binding_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
    write(out/'inputs.json',dict(frozen={str(p.relative_to(out)):sha(p)for folder in ['src','assets','runtime','oracles']for p in(out/folder).iterdir()if p.is_file()},
        executable_SHA256=sha(out/'application'),GPU_execution=False,core_runtime_linked=False,compute_CB_commit_supported=False))


def run(a):
    b,out=a.build.resolve(),a.out.resolve();m=read(b/'inputs.json');assert not out.exists()and out.parent.is_dir()
    for name,digest in m['frozen'].items():assert sha(b/name)==digest,name
    assert sha(b/'application')==m['executable_SHA256'];driver=check_driver_profile();out.mkdir();(out/'outputs').mkdir()
    for folder in ['src','assets','runtime','oracles']:shutil.copytree(b/folder,out/folder)
    shutil.copyfile(b/'application',out/'application');(out/'application').chmod(0o755)
    write(out/'inputs.json',dict(m,case=a.case,mode=a.mode,driver_SHA256=driver,source_build_inputs_SHA256=sha(b/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    args=[str(out/'assets'/(a.case+'.metallib')),a.case,str(out/'outputs'),a.mode]
    receipt=run_host(out/'application',out/'execution',args,a.reservation_root.resolve())
    write(out/'results.json',read(out/'execution/execution.stdout'))
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_native_command_binding import verify;print(json.dumps(verify(sys.argv[2])))'
    argv=[sys.executable,'-I','-c',code,str(out/'oracles'),str(out)]
    p=subprocess.run(argv,capture_output=True,text=True)
    (out/'verification.stdout').write_text(p.stdout);(out/'verification.stderr').write_text(p.stderr)
    write(out/'verification-execution.json',dict(argv=argv,exit_code=p.returncode,isolated_interpreter=True,code_SHA256=hashlib.sha256(code.encode()).hexdigest()))
    if p.returncode:raise RuntimeError('Inspect this terminal host and frozen oracle failure')
    proof=json.loads(p.stdout);write(out/'independent-verification.json',dict(proof,PID=receipt['pid']));print({k:v for k,v in proof.items()if k!='files_SHA256'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
    r=s.add_parser('run')
    for name in ['build','out','reservation-root']:r.add_argument('--'+name,type=Path,required=True)
    r.add_argument('--case',choices=CASES,required=True);r.add_argument('--mode',choices=MODES,required=True);r.set_defaults(func=run)
    a=p.parse_args();a.func(a)
