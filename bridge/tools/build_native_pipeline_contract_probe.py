#!/usr/bin/env python3
"""Freeze a native metadata/factory probe, with no experimental runtime linked."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/native-pipeline-command-client-build-20261015-02';base=json.loads((old/'inputs.json').read_text());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest();(out/'assets').mkdir()
for n in ['consumer.metallib','producer.metallib']:assert sha(old/'assets'/n)==base['assets_SHA256'][n];shutil.copyfile(old/'assets'/n,out/'assets'/n)
shutil.copytree(old/'runtime',out/'runtime');shutil.copyfile(ROOT/'tools/native_pipeline_contract_probe.mm',out/'native_pipeline_contract_probe.mm');shutil.copyfile(ROOT/'src/KeplerCommandIRReflection.inc',out/'KeplerCommandIRReflection.inc')
cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',str(out/'native_pipeline_contract_probe.mm'),'-framework','Metal','-framework','Foundation','-o',str(out/'application')];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/'build.stdout').write_text(r.stdout);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n');assert not r.returncode,r.stderr[-2500:]
(out/'inputs.json').write_text(json.dumps({'source_hashes':{n:sha(out/n)for n in ['native_pipeline_contract_probe.mm','KeplerCommandIRReflection.inc']},'assets_SHA256':{p.name:sha(p)for p in(out/'assets').iterdir()},'runtime_SHA256':{p.name:sha(p)for p in(out/'runtime').iterdir()if p.is_file()},'executable_SHA256':sha(out/'application'),'GPU_execution':False,'source_generator_SHA256':sha(__file__),'no_experimental_runtime':True},indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out)}))
