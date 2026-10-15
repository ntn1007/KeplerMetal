#!/usr/bin/env python3
"""Compile a non-dispatch public argument-encoder boundary witness."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
parent=ROOT/'results/command-ir-dataflow-client-build-20261015-04';inp=json.loads((parent/'inputs.json').read_text())
library=ROOT/'results/command-ir-dataflow-library-build-20261015-03';lm=json.loads((library/'manifest.json').read_text());assert sha(library/'libKeplerMetal.a')==lm['static_library_SHA256']=='d88158307ed566d1a048f7f729c2896419c6836b3f44899ab6711a59850456fc'
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'assets').mkdir();(out/'runtime').mkdir()
for n in ['consumer.metallib','consumer.json']:
 assert sha(parent/'assets'/n)==inp['assets_SHA256'][n];shutil.copyfile(parent/'assets'/n,out/'assets'/n)
for n,h in inp['runtime_SHA256'].items():assert sha(parent/'runtime'/n)==h;shutil.copyfile(parent/'runtime'/n,out/'runtime'/n)
assert sha(library/'src/KeplerCPUICB.h')==lm['source_SHA256']['src/KeplerCPUICB.h'];shutil.copyfile(library/'src/KeplerCPUICB.h',out/'KeplerCPUICB.h')
shutil.copyfile(ROOT/'tools/argument_encoder_boundary_probe.mm',out/'argument_encoder_boundary_probe.mm')
cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'argument_encoder_boundary_probe.mm'),str(library/'libKeplerMetal.a'),'-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/'build.stdout').write_text(r.stdout);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n');assert not r.returncode,r.stderr
inputs={'source_hashes':{n:sha(out/n)for n in ['argument_encoder_boundary_probe.mm','KeplerCPUICB.h']},'assets_SHA256':{x.name:sha(x)for x in(out/'assets').iterdir()},'runtime_SHA256':{x.name:sha(x)for x in(out/'runtime').iterdir()},'executable_SHA256':sha(out/'application'),'static_library_SHA256':sha(library/'libKeplerMetal.a'),'library_build_manifest_SHA256':sha(library/'manifest.json'),'source_generator_SHA256':sha(__file__),'GPU_execution':False}
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'executable_SHA256':inputs['executable_SHA256']}))
