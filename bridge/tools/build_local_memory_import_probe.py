#!/usr/bin/env python3
"""Freeze the native references and offline programs with the new MRC transport."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--native-build',type=Path,required=True);p.add_argument('--programs',type=Path,required=True);p.add_argument('--contracts',action='store_true');p.add_argument('--extended',action='store_true');a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);lib=a.library.resolve();native=a.native_build.resolve();programs=a.programs.resolve();lm=json.loads((lib/'manifest.json').read_text());nm=json.loads((native/'inputs.json').read_text());pm=json.loads((programs/'manifest.json').read_text());assert sha(lib/'libKeplerMetal.a')==lm['static_library_SHA256']
for n,h in nm['assets_SHA256'].items():assert sha(native/'assets'/n)==h
shutil.copytree(native/'assets',out/'assets');shutil.copytree(native/'runtime',out/'runtime')
for row in pm['programs']:
 assert sha(programs/(row['name']+'.sass'))==row['code_SHA256']
 for suffix in ['.sass','.json']:shutil.copyfile(programs/(row['name']+suffix),out/'assets'/(row['name']+suffix))
source='local_memory_contract_probe.mm'if a.contracts else'local_memory_probe.mm'
for s,n in [(ROOT/'tools'/source,source),(lib/'src/KeplerProgramImport.h','KeplerProgramImport.h')]:shutil.copyfile(s,out/n)
cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_LOCAL_IMPORT=1','-DKP_LOCAL_EXTENDED='+str(int(a.extended)),'-I',out,out/source,lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'];cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/'host.stdout').write_text(r.stdout);(out/'host.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n')
if r.returncode:print(r.stderr[-2500:]);raise SystemExit(r.returncode)
inputs={'source_hashes':{n:sha(out/n)for n in [source,'KeplerProgramImport.h']},'assets_SHA256':{p.name:sha(p)for p in(out/'assets').iterdir()},'runtime_SHA256':{p.name:sha(p)for p in(out/'runtime').iterdir()},'static_library_SHA256':sha(lib/'libKeplerMetal.a'),'library_manifest_SHA256':sha(lib/'manifest.json'),'programs_manifest_SHA256':sha(programs/'manifest.json'),'executable_SHA256':sha(out/'application'),'source_generator_SHA256':sha(__file__),'GPU_execution':False}
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(json.dumps({'status':'PASS','library_SHA256':inputs['static_library_SHA256']}))
