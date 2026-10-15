#!/usr/bin/env python3
"""Build the bounded IR-data probe; does not execute GPU work."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--compiler-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
source=a.compiler_build.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
manifest=json.loads((source/'manifest.json').read_text());assert manifest['status']=='PASS'
for path,h in manifest['input_SHA256'].items():assert sha(path)==h,path
for path,h in manifest['fork_SHA256'].items():assert sha(source/path)==h,path
for name in ['info.json','program.sass','program.asm']:shutil.copyfile(source/'backend-enabled'/name,out/name if name!='info.json' else out/'info.json')
(out/'backend-enabled').mkdir()
for name in ['info.json','program.sass']:shutil.copyfile(out/name,out/'backend-enabled'/name)
for path in [ROOT/'tools/command_ir_probe.mm',ROOT/'src/command_ir_carrier.metal',ROOT/'src/KeplerCommandIR.h',ROOT/'src/KeplerProgramImport.h',ROOT/'src/KeplerProgramImport.mm']:shutil.copyfile(path,out/path.name)
commands=[]
def run(argv,label):
 r=subprocess.run([str(x)for x in argv],capture_output=True,text=True,timeout=55)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'argv':[str(x)for x in argv],'label':label,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,r.stderr[-4000:]
run(['xcrun','metal','-std=macos-metal2.0','-c',out/'command_ir_carrier.metal','-o',out/'carrier.air'],'carrier-metal')
run(['xcrun','metallib',out/'carrier.air','-o',out/'command_ir_carrier.metallib'],'carrier-metallib')
run(['clang++','-arch','x86_64','-std=c++17','-O2','-I',out,out/'command_ir_probe.mm',out/'KeplerProgramImport.mm','-framework','Metal','-framework','Foundation','-o',out/'application'],'host')
(out/'runtime').mkdir()
sdk=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK'
for name in ['run_sdk_host.py','lab_gpu_reservation.py']:shutil.copyfile(sdk/'runtime'/name,out/'runtime'/name)
paths=[x for x in out.rglob('*')if x.is_file()]
(out/'inputs.json').write_text(json.dumps({'compiler_manifest_SHA256':sha(source/'manifest.json'),'files_SHA256':{str(x.relative_to(out)):sha(x)for x in paths},'gpu_execution':False,'job_ids':[]},indent=2)+'\n')
print(json.dumps({'status':'PASS','out':str(out),'gpu_execution':False}))
