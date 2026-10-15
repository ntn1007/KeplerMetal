#!/usr/bin/env python3
"""Freeze native local-memory sources, capture observer and shared launcher."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'assets').mkdir();(out/'runtime').mkdir()
for source in ['src/kepler_local_memory.metal','tools/local_memory_probe.mm','tools/compiler_output_trace.mm']:
 shutil.copyfile(ROOT/source,out/Path(source).name)
for name in ['run_sdk_host.py','lab_gpu_reservation.py']:
 source=ROOT/'sdk-combined/runtime'/name if name=='run_sdk_host.py'else ROOT/'tools'/name
 shutil.copyfile(source,out/'runtime'/name)
commands=[]
def run(label,cmd):
 cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 if r.returncode:print(r.stderr[-2500:]);raise SystemExit(r.returncode)
 print(label,'PASS',flush=True)
run('metal',['xcrun','metal','-std=macos-metal2.3','-c',out/'kepler_local_memory.metal','-o',out/'local_memory.air'])
run('metallib',['xcrun','metallib',out/'local_memory.air','-o',out/'assets/local_memory.metallib'])
for source,exe,arc in [('local_memory_probe.mm','application','-fobjc-arc'),('compiler_output_trace.mm','compiler_output_trace','-fno-objc-arc')]:
 run(exe,['clang++','-arch','x86_64','-O2','-std=c++17',arc,out/source,'-framework','Metal','-framework','Foundation','-o',out/exe])
inputs={'source_hashes':{n:sha(out/n)for n in ['kepler_local_memory.metal','local_memory_probe.mm','compiler_output_trace.mm']},'assets_SHA256':{'local_memory.metallib':sha(out/'assets/local_memory.metallib')},'runtime_SHA256':{n:sha(out/'runtime'/n)for n in ['run_sdk_host.py','lab_gpu_reservation.py']},'executable_SHA256':sha(out/'application'),'capture_executable_SHA256':sha(out/'compiler_output_trace'),'source_generator_SHA256':sha(__file__),'GPU_execution':False,'native_reference':True}
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'source_SHA256':inputs['source_hashes']}))
