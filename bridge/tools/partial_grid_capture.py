#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture existing native compiler output for two pinned kernels; no GPU dispatch."""
import argparse,json,os,shutil,struct,subprocess,sys
from pathlib import Path
from public_large_scratch import ROOT,commands,preflight,read,sha,write
from video_metal_resource_observer import check_profile
PINS={'depth0':('control_flow.metallib','6ef44d85fb6ed1a96f17e080ea3620455c80e336a00c0a7537c3d1087c7f8cdd'),
      'grid_coordinates':('cpu_icb_grid3d.metallib','5c35418c2465d1fa87396419c165ac33b5005937e8623fc40329fef30be99de0')}
NAMES=('compiler_output_trace.mm','partial_grid_capture.py','verify_partial_grid_capture.py','video_metal_resource_observer.py','public_large_scratch.py')
def extract(blob):
    if len(blob)<24:raise ValueError('Truncated compiler container')
    version,total=struct.unpack_from('<2I',blob)
    if version not in (7,8,9) or total!=len(blob):raise ValueError('Unqualified container')
    offset=8;seen=set();code=None;metadata=None
    for _ in range(32):
        if offset in seen or offset+16>len(blob):raise ValueError('Invalid section chain')
        seen.add(offset);step,kind,size=struct.unpack_from('<QII',blob,offset)
        if offset+16+size>len(blob):raise ValueError('Truncated section')
        data=blob[offset+16:offset+16+size]
        if kind==0x10004:
            if metadata is not None or size!=232:raise ValueError('Ambiguous metadata')
            metadata=data
        if kind==0x10005:
            if code is not None or not data or len(data)%64:raise ValueError('Ambiguous code')
            code=data
        if not step:break
        if step<16+size:raise ValueError('Invalid section step')
        offset+=step
    else:raise ValueError('Section limit exceeded')
    if metadata is None or code is None:raise ValueError('Missing metadata or code')
    return code

def build(a):
    out=a.out.resolve();preflight(out);profile=check_profile();inputs={'depth0':a.control.resolve(),'grid_coordinates':a.grid.resolve()};decoder=a.envydis.resolve();control_source=a.control_source.resolve();grid_source=ROOT/'src/cpu_icb_grid3d.metal'
    for name,path in inputs.items():
        if sha(path)!=PINS[name][1]:raise ValueError('Unqualified library: '+name)
    if sha(control_source)!='779b9d04dd80ab67f88230db983e3da84342478ee57f8bba616a8ef8e65797af' or sha(grid_source)!='ef339e5003982e38ba853a026b1e3a1300d30f365f319538eeb98ad38e991a9b':raise ValueError('Shader source changed')
    if not decoder.is_file() or not os.access(decoder,os.X_OK):raise ValueError('Existing envydis executable required')
    out.mkdir()
    for folder in ('src','assets','runtime'):(out/folder).mkdir()
    for name in NAMES:shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    for name,path in inputs.items():shutil.copyfile(path,out/'assets'/PINS[name][0])
    shutil.copyfile(control_source,out/'assets/control_flow.metal');shutil.copyfile(grid_source,out/'assets/cpu_icb_grid3d.metal')
    shutil.copyfile(decoder,out/'envydis');(out/'envydis').chmod(0o755)
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py');shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    run=commands(out);run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc',out/'src/compiler_output_trace.mm','-framework','Foundation','-framework','Metal','-o',out/'application'])
    frozen={str(p.relative_to(out)):sha(p) for folder in ('src','assets','runtime') for p in (out/folder).iterdir() if p.is_file()}
    write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':sha(out/'application'),'envydis_SHA256':sha(out/'envydis'),'profile':profile,'user_UID':os.getuid(),'GPU_dispatch':False})

def run(a):
    build,out=a.build.resolve(),a.out.resolve();data=read(build/'inputs.json')
    if out.exists() or not out.parent.is_dir():raise ValueError('Fresh output required')
    for name,digest in data['frozen'].items():
        if sha(build/name)!=digest:raise ValueError('Frozen input changed: '+name)
    if sha(build/'application')!=data['executable_SHA256'] or sha(build/'envydis')!=data['envydis_SHA256']:raise ValueError('Build artifact changed')
    for name in ('partial_grid_capture.py','video_metal_resource_observer.py','public_large_scratch.py'):
        if sha(ROOT/'tools'/name)!=data['frozen']['src/'+name]:raise ValueError('Executed coordinator changed: '+name)
    if check_profile()!=data['profile'] or os.getuid()!=data['user_UID']:raise ValueError('Profile or user changed')
    out.mkdir();shutil.copytree(build/'src',out/'src');shutil.copytree(build/'runtime',out/'runtime');shutil.copytree(build/'assets',out/'assets')
    for name in ('application','envydis'):shutil.copyfile(build/name,out/name);(out/name).chmod(0o755)
    (out/'capture').mkdir();write(out/'inputs.json',dict(data,function=a.function,build_inputs_SHA256=sha(build/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    run_host(out/'application',out/'execution',[str(out/'assets'/PINS[a.function][0]),str(out/'capture'),'compute',a.function],a.reservation_root.resolve())
    if check_profile()!=data['profile']:raise ValueError('Profile changed after host')
    r=read(out/'execution/execution.stdout');write(out/'results.json',r)
    if not r['pipeline_created'] or r['gpu_dispatch'] or len(r['captures'])!=1 or not r['captures'][0]['saved']:raise ValueError('Native observation failed')
    code=extract((out/'capture/program-0.compiler-output.bin').read_bytes());(out/'capture/native.sass').write_bytes(code)
    p=subprocess.run([str(out/'envydis'),'-m','gf100','-V','gk104','-i','-n',str(out/'capture/native.sass')],capture_output=True,text=True,timeout=30)
    (out/'disassembly.stdout').write_text(p.stdout);(out/'disassembly.stderr').write_text(p.stderr);write(out/'disassembly-execution.json',{'exit_code':p.returncode,'GPU_dispatch':False})
    if p.returncode:raise ValueError('SM30 decoder failed')
    v=subprocess.run([sys.executable,'-I',str(out/'src/verify_partial_grid_capture.py'),str(out)],capture_output=True,text=True,timeout=30)
    (out/'verification.stdout').write_text(v.stdout);(out/'verification.stderr').write_text(v.stderr);write(out/'verification-execution.json',{'exit_code':v.returncode,'isolated_interpreter':True})
    if v.returncode:raise RuntimeError('Capture oracle failed; inspect '+str(out/'verification.stderr'))
    print(v.stdout.strip())
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True);b=s.add_parser('build')
    for n in ('out','control','control-source','grid','envydis'):b.add_argument('--'+n,type=Path,required=True)
    b.set_defaults(func=build);r=s.add_parser('run')
    for n in ('build','out','reservation-root'):r.add_argument('--'+n,type=Path,required=True)
    r.add_argument('--function',choices=list(PINS),required=True);r.set_defaults(func=run);a=p.parse_args();a.func(a)
