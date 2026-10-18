#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Source-only optional resident-batch SDK build, explicit GPU run and CPU audit."""
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
def require(ok,text):
    if not ok:raise ValueError(text)
def within(path):
    p=Path(path).resolve();r=p.relative_to(ROOT/'build');require(r.parts,'named build/output required');return p
def verify(build):
    inputs=load(build/'inputs.json')
    for n,h in inputs['files_SHA256'].items():
        p=(build/n).resolve();p.relative_to(build);require(sha(p)==h,'frozen build input '+n)
    core=load(build/'core-manifest.json')
    require(core['status']=='PASS' and core['GPU_execution'] is False and len(core['object_SHA256'])==7 and core['static_library_SHA256']==sha(build/'libKeplerMetal.a'),'seven-object text-built core identity')
    for n,h in core['source_SHA256'].items():require(sha(build/'core-src'/n)==h,'frozen core source '+n)
    return inputs
def contract(build):
    path=build/'runtime/resident_batch_contract.py';i=verify(build)
    require(sha(path)==i['files_SHA256']['runtime/resident_batch_contract.py'],'frozen independent auditor identity')
    spec=importlib.util.spec_from_file_location('_resident_batch_contract',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def build(out,core):
    require(platform.system()=='Darwin' and platform.machine()=='x86_64','native Intel macOS/Xcode required')
    c=load(core/'manifest.json')
    require(c['status']=='PASS' and c['GPU_execution'] is False and len(c['object_SHA256'])==7 and sha(core/'libKeplerMetal.a')==c['static_library_SHA256'],'complete source core required')
    for n,h in c['source_SHA256'].items():require(sha(core/'src'/n)==h==sha(ROOT/'bridge/src'/n),'core/current source mismatch '+n)
    for n in ['KeplerResidentBatch.h','KeplerResidentBatch.mm']:require(n in c['source_SHA256'],'rebuild core snapshot after adding optional module')
    out.mkdir(parents=True,exist_ok=False);(out/'runtime').mkdir();shutil.copytree(core/'src',out/'core-src')
    sources={'native_resident_batch_probe.mm':ROOT/'examples/native_resident_batch_probe.mm',
        'native_concurrent_dispatch.metal':ROOT/'examples/native_concurrent_dispatch.metal',
        'manifest.json':ROOT/'profiles/native-resident-batch.json','core-manifest.json':core/'manifest.json',
        'libKeplerMetal.a':core/'libKeplerMetal.a','builder.py':Path(__file__),
        'runtime/resident_batch_contract.py':ROOT/'tools/resident_batch_contract.py',
        'runtime/run_sdk_host.py':ROOT/'bridge/sdk-combined/runtime/run_sdk_host.py',
        'runtime/lab_gpu_reservation.py':ROOT/'bridge/tools/lab_gpu_reservation.py'}
    for n,p in sources.items():shutil.copyfile(p,out/n)
    commands=[]
    def command(label,argv):
        r=subprocess.run(list(map(str,argv)),capture_output=True,timeout=90)
        (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
        commands.append(dict(label=label,argv=list(map(str,argv)),exit_code=r.returncode));write(out/'commands.json',commands)
        require(r.returncode==0,'build failed at '+label+'; retained stderr')
    command('metal',['xcrun','-sdk','macosx','metal','-std=macos-metal2.3','-c',out/'native_concurrent_dispatch.metal','-o',out/'probe.air'])
    command('metallib',['xcrun','-sdk','macosx','metallib',out/'probe.air','-o',out/'probe.metallib'])
    require(sha(out/'probe.metallib')==load(out/'manifest.json')['library_SHA256']=='479a0f85935823395174b25c0ead11482796389a5c8116cc7e5929d84ec0e7ed','regenerated shader must match qualified profile; no silent repin')
    common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-Wno-deprecated-declarations','-I',out/'core-src']
    command('extension',common+['-c',out/'core-src/KeplerResidentBatch.mm','-o',out/'KeplerResidentBatch.o'])
    command('host',common+[out/'native_resident_batch_probe.mm',out/'KeplerResidentBatch.o',out/'libKeplerMetal.a','-Wl,-ObjC','-framework','Foundation','-framework','Metal','-o',out/'application'])
    names=list(sources)+['probe.air','probe.metallib','KeplerResidentBatch.o','application']
    names.extend(str(p.relative_to(out)) for p in (out/'core-src').iterdir() if p.is_file())
    inputs=dict(files_SHA256={n:sha(out/n) for n in sorted(names)},core_source_compilations=0,optional_extension_compilations=1,
        core_rebuilt_separately_from_public_text=True,historical_qualification_inherited=False,GPU_execution=False,system_modified=False,
        SDK=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),
        toolchain=subprocess.check_output(['xcrun','clang++','--version'],text=True),platform=subprocess.check_output(['sw_vers'],text=True))
    write(out/'inputs.json',inputs);verify(out)
    print(json.dumps(dict(status='BUILT',core_SHA256=sha(out/'libKeplerMetal.a'),extension_SHA256=sha(out/'KeplerResidentBatch.o'),executable_SHA256=sha(out/'application'),GPU_execution=False)))
def run(build,out,mode,trials,reservation,baseline):
    auditor=contract(build);inputs=verify(build)
    require(reservation.is_dir() and (reservation/'results').is_dir(),'existing common host reservation root/results required')
    gate=None
    if mode!='prepare':
        require(baseline is not None,'run requires independently auditable --baseline directory')
        gate=auditor.audit(build,within(baseline));expected={'serial':('prepare',0),'segmented':('serial',56),'parallel':('segmented',34)}[mode]
        require(gate['mode']==expected[0] and gate['totals']['dispatches']>=expected[1],'wrong qualification prerequisite for '+mode)
    out.mkdir(parents=True,exist_ok=False);(out/'captures').mkdir();shutil.copyfile(build/'inputs.json',out/'inputs.json');shutil.copyfile(__file__,out/'launcher.py')
    if gate is not None:write(out/'baseline-gate.json',gate)
    sys.path.insert(0,str(build/'runtime'));from run_sdk_host import run_host
    m=run_host(build/'application',out/'execution',[str(build/'probe.metallib'),str(build/'manifest.json'),str(out/'captures'),mode,str(trials)],reservation)
    d=load(out/'execution/execution.stdout');require(m['exit_code']==0 and d['status']=='PASS','native run failed; preserve exact process and captures')
    write(out/'results.json',d);result=auditor.audit(build,out);write(out/'audit.json',result)
    print(json.dumps({k:result[k] for k in ['status','mode','trials','totals','per_kind']}))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','run','audit']);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--core-build',type=Path);p.add_argument('--build',type=Path);p.add_argument('--run',type=Path);p.add_argument('--baseline',type=Path)
    p.add_argument('--mode',choices=['prepare','serial','segmented','parallel'],default='prepare');p.add_argument('--trials',type=int,default=4);p.add_argument('--reservation-root',type=Path)
    a=p.parse_args();out=within(a.out);require(not out.exists() and 1<=a.trials<=4,'fresh output and1..4trials required')
    if a.action=='build':
        if not a.core_build:p.error('build requires --core-build from tools/build_from_source.py')
        build(out,within(a.core_build))
    elif a.action=='run':
        if not a.build or not a.reservation_root:p.error('run requires --build and --reservation-root')
        run(within(a.build),out,a.mode,a.trials,a.reservation_root.resolve(),a.baseline)
    else:
        if not a.build or not a.run:p.error('audit requires --build and --run')
        result=contract(within(a.build)).audit(within(a.build),within(a.run));write(out,result);print(json.dumps(result))
if __name__=='__main__':main()
