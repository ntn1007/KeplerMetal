#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build/run/audit the reference GTX880M resident-overlap experiment from text."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def require(v,m):
    if not v:raise ValueError(m)

def within_build(path):
    path=Path(path).resolve();relative=path.relative_to(ROOT/'build')
    require(relative.parts,'a named fresh build/output directory is required');return path

def contract(build):
    path=build/'runtime/resident_overlap_contract.py';inputs=load(build/'inputs.json')
    require(sha(path)==inputs['files_SHA256']['runtime/resident_overlap_contract.py'],'frozen verifier differs')
    spec=importlib.util.spec_from_file_location('_frozen_resident_overlap_contract',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def build(out,core):
    require(platform.system()=='Darwin' and platform.machine()=='x86_64','native Intel macOS/Xcode build required')
    core=within_build(core);cm=load(core/'manifest.json')
    require(cm['status']=='PASS' and sha(core/'libKeplerMetal.a')==cm['static_library_SHA256'],'complete source-built core required')
    for name,digest in cm['source_SHA256'].items():
        require(sha(core/'src'/name)==digest==sha(ROOT/'bridge/src'/name),'core/repository source mismatch: '+name)
    out.mkdir(parents=True,exist_ok=False);(out/'runtime').mkdir();shutil.copytree(core/'src',out/'core-src')
    sources={'native_resident_pair_probe.mm':ROOT/'examples/native_resident_pair_probe.mm',
        'native_concurrent_dispatch.metal':ROOT/'examples/native_concurrent_dispatch.metal',
        'libKeplerMetal.a':core/'libKeplerMetal.a','core-manifest.json':core/'manifest.json','builder.py':Path(__file__),
        'runtime/run_sdk_host.py':ROOT/'bridge/sdk-combined/runtime/run_sdk_host.py',
        'runtime/lab_gpu_reservation.py':ROOT/'bridge/tools/lab_gpu_reservation.py',
        'runtime/resident_overlap_contract.py':ROOT/'tools/resident_overlap_contract.py'}
    for name,source in sources.items():shutil.copyfile(source,out/name)
    commands=[]
    def command(label,argv):
        r=subprocess.run(list(map(str,argv)),capture_output=True,timeout=90)
        (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
        commands.append(dict(label=label,argv=list(map(str,argv)),exit_code=r.returncode));write(out/'commands.json',commands)
        require(r.returncode==0,'build failed at '+label+'; inspect retained stderr')
    command('metal',['xcrun','-sdk','macosx','metal','-std=macos-metal2.3','-c',out/'native_concurrent_dispatch.metal','-o',out/'probe.air'])
    command('metallib',['xcrun','-sdk','macosx','metallib',out/'probe.air','-o',out/'probe.metallib'])
    functions=[]
    for name in ['observe_a','observe_b']:
        functions.append(dict(name=name,buffers=[
            dict(name='sync',index=0,data_size=4,alignment=4,data_type=1,access=1,minimum_bytes=12,per_invocation_bytes=0),
            dict(name='out',index=1,data_size=4,alignment=4,data_type=33,access=1,minimum_bytes=32,per_invocation_bytes=32),
            dict(name='cfg',index=2,data_size=16,alignment=256,data_type=1,access=0,minimum_bytes=512,per_invocation_bytes=0)],
            constant_buffer_index=2,static_threadgroup_bytes=0,max_local=1,max_invocations=1,qmd_register_count=17,
            allow_multidimensional=False,native_literal_bank_0=dict(bytes=256,address_relation='native_code_end_aligned_256')))
    write(out/'manifest.json',dict(schema=2,library_SHA256=sha(out/'probe.metallib'),functions=functions))
    command('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-Wno-deprecated-declarations',
        '-I',out/'core-src',out/'native_resident_pair_probe.mm',out/'libKeplerMetal.a','-Wl,-ObjC',
        '-framework','Foundation','-framework','Metal','-o',out/'application'])
    names=list(sources)+['probe.air','probe.metallib','manifest.json','application']
    names.extend(str(p.relative_to(out)) for p in (out/'core-src').iterdir() if p.is_file())
    inputs=dict(files_SHA256={n:sha(out/n) for n in sorted(names)},core_source_compilations=0,
        core_was_rebuilt_from_public_text=True,historical_GPU_qualification_inherited=False,
        SDK=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip(),
        toolchain=subprocess.check_output(['xcrun','clang++','--version'],text=True),
        platform=subprocess.check_output(['sw_vers'],text=True),GPU_execution=False,system_modified=False)
    write(out/'inputs.json',inputs)
    print(json.dumps(dict(status='BUILT',archive_SHA256=sha(out/'libKeplerMetal.a'),metallib_SHA256=sha(out/'probe.metallib'),GPU_execution=False)))

def run(build,out,mode,trials,reservation,baseline):
    verifier=contract(build);inputs=verifier.verify_build(build)
    require(reservation.is_dir() and (reservation/'results').is_dir(),'explicit existing common reservation root/results required')
    gate=None
    if mode=='overlap':
        require(baseline is not None,'overlap requires --baseline from this exact build')
        gate=verifier.audit_capture(build,within_build(baseline))
        require(gate['mode']=='serial' and gate['trials']>=20 and gate['totals']['dispatches']>=24,'independent four-trial serial qualification required')
    out.mkdir(parents=True,exist_ok=False);(out/'captures').mkdir();shutil.copyfile(build/'inputs.json',out/'inputs.json')
    shutil.copyfile(__file__,out/'launcher.py')
    if gate is not None:write(out/'baseline-gate.json',gate)
    sys.path.insert(0,str(build/'runtime'));from run_sdk_host import run_host
    m=run_host(build/'application',out/'execution',[str(build/'probe.metallib'),str(build/'manifest.json'),str(out/'captures'),mode,str(trials)],reservation)
    result=load(out/'execution/execution.stdout')
    require(result['pid']==m['pid'] and result['status']=='PASS','native test failed; preserve and inspect this exact process capture')
    write(out/'results.json',result);summary=verifier.audit_capture(build,out);write(out/'audit.json',summary)
    print(json.dumps(summary))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','run','audit'])
    p.add_argument('--out',required=True,type=Path);p.add_argument('--core-build',type=Path);p.add_argument('--build',type=Path)
    p.add_argument('--run',type=Path);p.add_argument('--baseline',type=Path);p.add_argument('--reservation-root',type=Path)
    p.add_argument('--mode',choices=['prepare','serial','overlap'],default='prepare');p.add_argument('--trials',type=int,default=4)
    a=p.parse_args();out=within_build(a.out);require(not out.exists(),'fresh output required');require(1<=a.trials<=8,'1..8 bounded trials required')
    if a.action=='build':
        if not a.core_build:p.error('build requires --core-build from tools/build_from_source.py')
        build(out,a.core_build)
    elif a.action=='run':
        if not a.build or not a.reservation_root:p.error('run requires --build and --reservation-root')
        run(within_build(a.build),out,a.mode,a.trials,a.reservation_root.resolve(),a.baseline)
    else:
        if not a.build or not a.run:p.error('audit requires --build and --run')
        result=contract(within_build(a.build)).audit_capture(within_build(a.build),within_build(a.run));write(out,result);print(json.dumps(result))

if __name__=='__main__':main()
