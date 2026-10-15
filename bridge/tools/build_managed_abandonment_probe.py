#!/usr/bin/env python3
"""Reuse frozen MRC import object/assets; compile only the new ARC witness."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
old=ROOT/'results/graphics-factory-lifetime-client-build-20261015-02';m=json.loads((old/'inputs.json').read_text())
for n,h in m['source_hashes'].items():assert sha(old/n)==h
assert sha(old/'KeplerProgramImport.o')==m['import_object_SHA256']
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
for n in ['KeplerProgramImport.h','KeplerProgramImport.mm','KeplerProgramImport.o']:shutil.copyfile(old/n,out/n)
shutil.copytree(old/'assets',out/'assets');shutil.copytree(old/'runtime',out/'runtime')
shutil.copyfile(ROOT/'tools/managed_abandonment_probe.mm',out/'managed_abandonment_probe.mm')
cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'managed_abandonment_probe.mm'),str(out/'KeplerProgramImport.o'),'-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
(out/'build.stdout').write_text(r.stdout);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n');assert not r.returncode,r.stderr
inputs={'source_hashes':{n:sha(out/n)for n in ['managed_abandonment_probe.mm','KeplerProgramImport.h','KeplerProgramImport.mm']},'assets_SHA256':{n:sha(out/'assets'/n)for n in m['assets_SHA256']},'runtime_SHA256':{n:sha(out/'runtime'/n)for n in m['runtime_SHA256']},'executable_SHA256':sha(out/'application'),'import_object_SHA256':sha(out/'KeplerProgramImport.o'),'frozen_parent_inputs_SHA256':sha(old/'inputs.json'),'source_generator_SHA256':sha(__file__),'GPU_execution':False}
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'inputs':inputs}))
