#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture and qualify physical and logical built-in data for bounded grid edges."""
import argparse,os,shutil,subprocess,sys
from pathlib import Path
from public_large_scratch import ROOT,commands,preflight,read,sha,write
from video_metal_resource_observer import check_profile
PIN='1e89eaf47bdcb482e4fc760869b6005e47c1e836ec43e14820ba601c28fdd3f5'
NAMES=('partial_chain_barrier_probe.mm','partial_chain_barrier.py','verify_partial_chain_barrier.py','verify_partial_assembly_3d.py','decode_native_commands.py','video_metal_resource_observer.py','public_large_scratch.py')

def build(a):
    out=a.out.resolve();source=a.archive.resolve();library=a.metallib.resolve();preflight(out);profile=check_profile();m=read(source/'manifest.json')
    if m['status']!='PASS' or m['architecture']!='x86_64' or m['SDK']!='26.2' or sha(source/'libKeplerMetal.a')!=m['static_library_SHA256'] or sha(library)!=PIN:raise ValueError('Unqualified archive or native Metal library')
    for name,digest in m['source_SHA256'].items():
        if sha(source/'src'/name)!=digest or sha(ROOT/'src'/name)!=digest:raise ValueError('Archive source changed: '+name)
    out.mkdir()
    for folder in ('src','runtime','assets'):(out/folder).mkdir()
    for name in NAMES:shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    for name in m['source_SHA256']:shutil.copyfile(source/'src'/name,out/'src'/name)
    shutil.copyfile(source/'libKeplerMetal.a',out/'runtime_archive.a');shutil.copyfile(source/'manifest.json',out/'archive-manifest.json')
    shutil.copyfile(library,out/'assets/partial_wide_barrier.metallib');shutil.copyfile(ROOT/'src/partial_wide_barrier.json',out/'assets/partial_wide_barrier.json')
    if sha(out/'assets/partial_wide_barrier.json')!='31287315ccb87740c86c7180651007a766535bfcadf3de34edbe10e6bad233be':raise ValueError('3D manifest changed')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py');shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    run=commands(out);run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src',out/'src/partial_chain_barrier_probe.mm','-Wl,-all_load',out/'runtime_archive.a','-framework','Metal','-framework','Foundation','-o',out/'application'])
    frozen={str(p.relative_to(out)):sha(p) for folder in ('src','runtime') for p in (out/folder).iterdir() if p.is_file()}
    frozen['archive-manifest.json']=sha(out/'archive-manifest.json')
    write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':sha(out/'application'),'runtime_archive_SHA256':sha(out/'runtime_archive.a'),'library_SHA256':sha(out/'assets/partial_wide_barrier.metallib'),'manifest_SHA256':sha(out/'assets/partial_wide_barrier.json'),'profile':profile,'user_UID':os.getuid(),'build_submitted_GPU_work':False})

def run(a):
    build,out=a.build.resolve(),a.out.resolve();data=read(build/'inputs.json')
    if out.exists() or not out.parent.is_dir() or not(0<a.registry_id<2**64):raise ValueError('Fresh output and registry ID required')
    for name,digest in data['frozen'].items():
        if sha(build/name)!=digest:raise ValueError('Frozen input changed: '+name)
    for name,digest in [('application',data['executable_SHA256']),('runtime_archive.a',data['runtime_archive_SHA256']),('assets/partial_wide_barrier.metallib',data['library_SHA256']),('assets/partial_wide_barrier.json',data['manifest_SHA256'])]:
        if sha(build/name)!=digest:raise ValueError('Build artifact changed: '+name)
    for name in ('partial_chain_barrier.py','video_metal_resource_observer.py','public_large_scratch.py'):
        if sha(ROOT/'tools'/name)!=data['frozen']['src/'+name]:raise ValueError('Executed coordinator changed: '+name)
    if check_profile()!=data['profile'] or os.getuid()!=data['user_UID']:raise ValueError('Profile or user changed')
    out.mkdir();shutil.copytree(build/'src',out/'src');shutil.copytree(build/'runtime',out/'runtime');shutil.copytree(build/'assets',out/'assets')
    for name in ('application','runtime_archive.a','archive-manifest.json'):shutil.copyfile(build/name,out/name)
    (out/'application').chmod(0o755);(out/'outputs').mkdir();write(out/'inputs.json',dict(data,mode=a.mode,case_index=a.case_index,registry_id=a.registry_id,build_inputs_SHA256=sha(build/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    run_host(out/'application',out/'execution',[str(out/'assets/partial_wide_barrier.metallib'),str(out/'assets/partial_wide_barrier.json'),str(out/'outputs'),a.mode,str(a.registry_id),str(a.case_index)],a.reservation_root.resolve())
    if check_profile()!=data['profile']:raise ValueError('Profile changed after host; preserve evidence')
    write(out/'results.json',read(out/'execution/execution.stdout'))
    p=subprocess.run([sys.executable,'-I',str(out/'src/verify_partial_chain_barrier.py'),str(out)],capture_output=True,text=True,timeout=60)
    (out/'verification.stdout').write_text(p.stdout);(out/'verification.stderr').write_text(p.stderr);write(out/'verification-execution.json',{'exit_code':p.returncode,'isolated_interpreter':True})
    if p.returncode:raise RuntimeError('Independent CPU oracle failed; inspect '+str(out/'verification.stderr'))
    print(p.stdout.strip())
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(required=True);b=sub.add_parser('build');b.add_argument('--out',type=Path,required=True);b.add_argument('--archive',type=Path,required=True);b.add_argument('--metallib',type=Path,required=True);b.set_defaults(func=build)
    r=sub.add_parser('run')
    for n in ('build','out','reservation-root'):r.add_argument('--'+n,type=Path,required=True)
    r.add_argument('--case-index',type=int,choices=range(8),required=True);r.add_argument('--mode',choices=['prepare','execute'],required=True);r.add_argument('--registry-id',type=int,required=True);r.set_defaults(func=run);a=p.parse_args();a.func(a)
