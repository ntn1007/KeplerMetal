#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build, inspect/certify, then explicitly run one exact AIR reset profile."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from public_large_scratch import ROOT, commands, preflight, check_driver_profile, read, sha, write
from public_native_command_boundary import source
from metallib_air import extract
from lower_air_render_reset import lower, AIR_SHA256, PROFILE


def build(a):
    out=a.out.resolve();preflight(out);out.mkdir()
    for name in ['src','assets','runtime','oracles']:(out/name).mkdir()
    for name in ['air_render_reset_probe.mm','NativeCommandBoundaryCapture.inc','lower_air_render_reset.py',
                 'public_air_render_reset.py','public_native_command_boundary.py','metallib_air.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    for name in ['KeplerGPUIdentity.h','air_render_reset_reference.metal']:
        shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['verify_air_render_reset.py','verify_native_command_boundary.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    run=commands(out);original=out/'src/typed_render_reset.metal'
    original.write_text('// SPDX-License-Identifier: MIT\n'+source('typed_render_reset'))
    run('original-metal',['xcrun','metal','-std=macos-metal2.3','-fmodules=none','-c',original,'-o',out/'original.air'])
    run('original-metallib',['xcrun','metallib',out/'original.air','-o',out/'assets/original.metallib'])
    module=extract((out/'assets/original.metallib').read_bytes(),'probe_boundary')
    if module['sha256']!=AIR_SHA256:raise ValueError('Original AIR differs: qualify toolchain/profile; do not repin silently')
    (out/'original-extracted.air').write_bytes(module['wrapped_AIR'])
    run('original-disassemble',['xcrun','metal','-S','-emit-llvm','-x','ir',out/'original-extracted.air','-o',out/'original.ll'])
    (out/'assets/lowered.ll.txt').write_text(lower((out/'original.ll').read_text()))
    run('lowered-air',['xcrun','metal','-x','ir','-O2','-c',out/'assets/lowered.ll.txt','-o',out/'lowered.air'])
    run('lowered-metallib',['xcrun','metallib',out/'lowered.air','-o',out/'assets/lowered.metallib'])
    run('lowered-IR',['xcrun','metal','-S','-emit-llvm','-x','ir',out/'lowered.air','-o',out/'assets/optimized.ll.txt'])
    optimized=(out/'assets/optimized.ll.txt').read_text()
    assert '@air.reset_render_command'not in optimized and '@kp_reset_render_command'not in optimized,'Inlining required'
    run('reference-air',['xcrun','metal','-std=macos-metal2.3','-fmodules=none','-c',out/'src/air_render_reset_reference.metal','-o',out/'reference.air'])
    run('reference-metallib',['xcrun','metallib',out/'reference.air','-o',out/'assets/reference.metallib'])
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out/'src',out/'src/air_render_reset_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
    write(out/'inputs.json',dict(profile=PROFILE,original_AIR_SHA256=module['sha256'],
        frozen={str(p.relative_to(out)):sha(p)for folder in ['src','runtime','oracles','assets']for p in(out/folder).iterdir()if p.is_file()},
        executable_SHA256=sha(out/'application'),core_runtime_linked=False))


def run(a):
    b,out=a.build.resolve(),a.out.resolve();m=read(b/'inputs.json')
    assert not out.exists()and out.parent.is_dir()
    for name,digest in m['frozen'].items():assert sha(b/name)==digest,name
    assert sha(b/'application')==m['executable_SHA256'];driver=check_driver_profile()
    if a.mode!='inspect':
        assert a.certificate and read(a.certificate)['driver_SHA256']==driver
        assert read(a.certificate)['library_SHA256']==sha(b/'assets'/(a.variant+'.metallib'))
    out.mkdir();(out/'outputs').mkdir()
    for folder in ['src','runtime','oracles','assets']:shutil.copytree(b/folder,out/folder)
    shutil.copyfile(b/'application',out/'application');(out/'application').chmod(0o755)
    if a.certificate:shutil.copyfile(a.certificate,out/'certificate.json')
    m.update(variant=a.variant,mode=a.mode,driver_SHA256=driver,source_build_inputs_SHA256=sha(b/'inputs.json'),certificate_SHA256=sha(out/'certificate.json')if a.certificate else None)
    write(out/'inputs.json',m)
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    args=[str(out/'assets'/(a.variant+'.metallib')),a.mode,str(out/'outputs'),str(out/'certificate.json')]
    receipt=run_host(out/'application',out/'execution',args,a.reservation_root.resolve())
    write(out/'results.json',read(out/'execution/execution.stdout'))
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_air_render_reset import verify;print(json.dumps(verify(sys.argv[2])))'
    argv=[sys.executable,'-I','-c',code,str(out/'oracles'),str(out)]
    p=subprocess.run(argv,capture_output=True,text=True)
    (out/'verification.stdout').write_text(p.stdout);(out/'verification.stderr').write_text(p.stderr)
    write(out/'verification-execution.json',dict(argv=argv,exit_code=p.returncode,isolated_interpreter=True))
    if p.returncode:raise RuntimeError('Frozen oracle failed; inspect exact terminal host')
    proof=json.loads(p.stdout);write(out/'independent-verification.json',dict(proof,PID=receipt['pid']));print(proof)


def certify(a):
    from verify_air_render_reset import verify, native_code
    out=a.run.resolve();proof=verify(out);assert proof['mode']=='inspect'
    d=read(out/'results.json');code,metadata=native_code(out)
    binary=a.envydis.resolve();(out/'native-code.bin').write_bytes(code)
    argv=[str(binary),'-m','gf100','-V','gk104','-i','-n',str(out/'native-code.bin')]
    p=subprocess.run(argv,capture_output=True,text=True,timeout=30)
    (out/'native-code.sass.txt').write_text(p.stdout);(out/'envydis.stderr').write_text(p.stderr)
    assert p.returncode==0 and p.stdout and not re.search(r'\bcall\b|\?\?\?',p.stdout,re.I),'Native code needs review; never execute unresolved operations'
    assert not any((int.from_bytes(code[i:i+8],'little')&0xf800000000004007)==0x5000000000000007 for i in range(8,len(code),8)if i%64),'Unresolved CALL refused'
    write(out/'certificate.json',dict(profile=PROFILE,library_SHA256=d['library_SHA256'],code_SHA256=d['code_SHA256'],
        driver_SHA256=read(out/'inputs.json')['driver_SHA256'],no_native_call=True,code_bytes=len(code),
        inspection_inputs_SHA256=sha(out/'inputs.json'),inspection_results_SHA256=sha(out/'results.json'),
        envydis_SHA256=sha(binary),envydis_argv=argv,disassembly_SHA256=sha(out/'native-code.sass.txt'),metadata_words=metadata))
    print(dict(status='OFFLINE_CERTIFIED',code_bytes=len(code),code_SHA256=d['code_SHA256']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
    r=s.add_parser('run')
    for name in ['build','out','reservation-root']:r.add_argument('--'+name,type=Path,required=True)
    r.add_argument('--variant',choices=['lowered','reference'],required=True);r.add_argument('--mode',choices=['inspect','execute','no_dispatch'],required=True)
    r.add_argument('--certificate',type=Path);r.set_defaults(func=run)
    c=s.add_parser('certify');c.add_argument('--run',type=Path,required=True);c.add_argument('--envydis',type=Path,required=True);c.set_defaults(func=certify)
    a=p.parse_args();a.func(a)
