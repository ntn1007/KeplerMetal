#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify user-mode nvAccelerator type-3 open/close on one exact profile.

No external method or command buffer is sent. This is an isolated open/close
witness, not an authorization of the separate privileged RM client or a video
engine test. Every native host is signed and uses the common GPU reservation.
"""
import argparse, json, os, platform, shutil, subprocess, sys
from pathlib import Path
from public_large_scratch import ROOT, commands, preflight, read, sha, write

PINS = {
 '/System/Library/Extensions/NVDAResman.kext/Contents/MacOS/NVDAResman':'36396eaecd68ddbb0482f019f38ce55d01b10379ca829da7f19b3bd8f3e26808',
 '/System/Library/Extensions/NVDAGK100Hal.kext/Contents/MacOS/NVDAGK100Hal':'74575453948c834dba5f18e936a58f611f01c598955ecc0f1ff79a501971c99e',
 '/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce':'44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3',
 '/System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2':'37e563d6cf3626101f30b1727a4f60dec02152dff9c74c0269c30c213a7320c8'}
LOADED = {
 'com.apple.nvidia.driver.NVDAResman':'879FE28C-BC88-3553-B3C7-1CCFAE357D45',
 'com.apple.nvidia.driver.NVDAGK100Hal':'CCDFB15A-E29E-38CE-A6C0-732F5648BC28',
 'com.apple.GeForce':'B907167E-E164-36D8-9E8F-695A72E738F7',
 'com.apple.iokit.IOAcceleratorFamily2':'6C4A16B1-66DC-3A8B-9F0B-D3E027B16EB1'}
KERNEL_UUID = '1291D44A-C0CD-3AC7-A9E4-CA2749B33959'


def check_profile():
    if platform.system() != 'Darwin' or platform.machine() != 'x86_64' or not os.getuid() or os.getuid() != os.geteuid():
        raise ValueError('Expected an unprivileged x86_64 Darwin user')
    for path,digest in PINS.items():
        if sha(path) != digest:
            raise ValueError('Exact video-context profile changed: '+path)
    kernel = subprocess.check_output(['sysctl','-n','kern.uuid'],text=True).strip()
    if kernel != KERNEL_UUID:
        raise ValueError('Kernel UUID changed')
    p = subprocess.run(['kextstat','-l'],capture_output=True,text=True,timeout=30)
    if p.returncode:
        raise ValueError('Loaded kext inventory unavailable')
    rows = {}
    for bundle,uuid in LOADED.items():
        found = [line for line in p.stdout.splitlines() if bundle in line and uuid in line]
        if len(found) != 1:
            raise ValueError('Loaded kext UUID absent or ambiguous: '+bundle)
        rows[bundle] = uuid
    return {'system_files_SHA256':PINS,'kernel_UUID':kernel,'loaded_kext_UUID':rows,
            'loaded_code_bytes_compared':False}


def build(a):
    out=a.out.resolve();preflight(out);profile=check_profile();out.mkdir()
    for x in ('src','runtime'):(out/x).mkdir()
    for name in ('video_context_probe.mm','video_context_current.py','verify_video_context_current.py','public_large_scratch.py'):
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    run=commands(out)
    run('build',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-Wno-deprecated-declarations',out/'src/video_context_probe.mm','-framework','Foundation','-framework','IOKit','-o',out/'application'])
    frozen={str(p.relative_to(out)):sha(p) for folder in ('src','runtime') for p in (out/folder).iterdir() if p.is_file()}
    write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':sha(out/'application'),
         'profile':profile,'user_UID':os.getuid(),'GPU_execution':False,'external_methods':False})


def run(a):
    build,out=a.build.resolve(),a.out.resolve();data=read(build/'inputs.json')
    if out.exists() or not out.parent.is_dir():raise ValueError('Fresh output path required')
    if a.mode == 'video' and not (0<a.registry_id<2**64):raise ValueError('Fresh registry ID required')
    for name,digest in data['frozen'].items():
        if sha(build/name)!=digest:raise ValueError('Frozen input changed: '+name)
    if sha(build/'application')!=data['executable_SHA256']:raise ValueError('Executable changed')
    for name in ('video_context_current.py','public_large_scratch.py'):
        if sha(ROOT/'tools'/name)!=data['frozen']['src/'+name]:raise ValueError('Executed coordinator changed: '+name)
    if check_profile()!=data['profile'] or os.getuid()!=data['user_UID']:raise ValueError('Profile or user changed')
    out.mkdir();shutil.copytree(build/'src',out/'src');shutil.copytree(build/'runtime',out/'runtime');shutil.copyfile(build/'application',out/'application');(out/'application').chmod(0o755)
    target = 0 if a.mode=='inventory' else 1 if a.mode=='wrong-target' else a.registry_id
    mode = 'inventory' if a.mode=='inventory' else 'video'
    write(out/'inputs.json',dict(data,mode=a.mode,registry_id=target,build_inputs_SHA256=sha(build/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    host=run_host(out/'application',out/'execution',[mode,str(target)],a.reservation_root.resolve())
    if check_profile()!=data['profile']:raise ValueError('Profile changed after host; preserve evidence')
    write(out/'results.json',read(out/'execution/execution.stdout'))
    p=subprocess.run([sys.executable,'-I',str(out/'src/verify_video_context_current.py'),str(out)],capture_output=True,text=True)
    (out/'verification.stdout').write_text(p.stdout);(out/'verification.stderr').write_text(p.stderr)
    write(out/'verification-execution.json',{'exit_code':p.returncode,'isolated_interpreter':True})
    if p.returncode:raise RuntimeError('Offline oracle failed; inspect '+str(out/'verification.stderr'))
    print(p.stdout.strip())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(required=True);b=sub.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
    r=sub.add_parser('run')
    for n in ('build','out','reservation-root'):r.add_argument('--'+n,type=Path,required=True)
    r.add_argument('--mode',choices=['inventory','wrong-target','video'],required=True);r.add_argument('--registry-id',type=int,default=0);r.set_defaults(func=run);a=p.parse_args();a.func(a)
