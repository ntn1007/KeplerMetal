#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded native GPU read/write on a Metal buffer after purge restoration."""
import argparse, os, shutil, subprocess, sys
from pathlib import Path
from public_large_scratch import ROOT, commands, preflight, read, sha, write
from video_metal_resource_observer import check_profile

NAMES=('video_metal_purge_gpu.mm','video_metal_purge_gpu.py','verify_video_metal_purge_gpu.py','video_metal_resource_observer.py','public_large_scratch.py')

def build(a):
    out=a.out.resolve();preflight(out);profile=check_profile();out.mkdir()
    for folder in ('src','runtime','assets'):(out/folder).mkdir()
    for name in NAMES:shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    shutil.copyfile(ROOT/'src/resource_sync_probe.metal',out/'src/resource_sync_probe.metal')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    run=commands(out)
    run('metal',['xcrun','-sdk','macosx','metal','-std=macos-metal2.0','-c',out/'src/resource_sync_probe.metal','-o',out/'resource_sync.air'])
    run('metallib',['xcrun','-sdk','macosx','metallib',out/'resource_sync.air','-o',out/'assets/resource_sync.metallib'])
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-Wno-deprecated-declarations',out/'src/video_metal_purge_gpu.mm','-framework','Foundation','-framework','IOKit','-framework','Metal','-o',out/'application'])
    frozen={str(p.relative_to(out)):sha(p) for folder in ('src','runtime') for p in (out/folder).iterdir() if p.is_file()}
    write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':sha(out/'application'),'metallib_SHA256':sha(out/'assets/resource_sync.metallib'),
                             'profile':profile,'user_UID':os.getuid(),'build_submitted_GPU_work':False})

def run(a):
    build,out=a.build.resolve(),a.out.resolve();data=read(build/'inputs.json')
    if out.exists() or not out.parent.is_dir() or not(0<a.registry_id<2**64):raise ValueError('Fresh output and registry ID required')
    for name,digest in data['frozen'].items():
        if sha(build/name)!=digest:raise ValueError('Frozen input changed: '+name)
    if sha(build/'application')!=data['executable_SHA256'] or sha(build/'assets/resource_sync.metallib')!=data['metallib_SHA256']:raise ValueError('Compiled input changed')
    for name in ('video_metal_purge_gpu.py','video_metal_resource_observer.py','public_large_scratch.py'):
        if sha(ROOT/'tools'/name)!=data['frozen']['src/'+name]:raise ValueError('Executed coordinator changed: '+name)
    if check_profile()!=data['profile'] or os.getuid()!=data['user_UID']:raise ValueError('Profile or user changed')
    if shutil.disk_usage(out.parent).free<512*1024**2:raise ValueError('Insufficient space for retained outputs')
    out.mkdir();shutil.copytree(build/'src',out/'src');shutil.copytree(build/'runtime',out/'runtime');shutil.copytree(build/'assets',out/'assets');shutil.copyfile(build/'application',out/'application');(out/'application').chmod(0o755);(out/'outputs').mkdir()
    write(out/'inputs.json',dict(data,mode=a.mode,registry_id=a.registry_id,build_inputs_SHA256=sha(build/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    run_host(out/'application',out/'execution',[a.mode,str(a.registry_id),str(out/'assets/resource_sync.metallib'),str(out/'outputs')],a.reservation_root.resolve())
    if check_profile()!=data['profile']:raise ValueError('Profile changed after host; preserve evidence')
    if sha(out/'assets/resource_sync.metallib')!=data['metallib_SHA256']:raise ValueError('Loaded library changed')
    write(out/'results.json',read(out/'execution/execution.stdout'))
    p=subprocess.run([sys.executable,'-I',str(out/'src/verify_video_metal_purge_gpu.py'),str(out)],capture_output=True,text=True,timeout=120)
    (out/'verification.stdout').write_text(p.stdout);(out/'verification.stderr').write_text(p.stderr)
    write(out/'verification-execution.json',{'exit_code':p.returncode,'isolated_interpreter':True})
    if p.returncode:raise RuntimeError('Independent CPU oracle failed; inspect '+str(out/'verification.stderr'))
    print(p.stdout.strip())

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(required=True);b=sub.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
    r=sub.add_parser('run')
    for n in ('build','out','reservation-root'):r.add_argument('--'+n,type=Path,required=True)
    r.add_argument('--mode',choices=['native','purge','negative'],required=True);r.add_argument('--registry-id',type=int,required=True);r.set_defaults(func=run);a=p.parse_args();a.func(a)
