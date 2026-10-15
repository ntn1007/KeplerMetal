#!/usr/bin/env python3
"""Compile only this adapted application, link the delivered static SDK."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
SDK=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
argv=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(SDK/'include'),str(SDK/'examples/client.mm'),'-L',str(SDK/'lib'),'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/'build.stderr').write_text(r.stderr);(out/'build.stdout').write_text(r.stdout);(out/'commands.json').write_text(json.dumps([{'argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr
for source,name in [(SDK/'examples/client.mm','client.mm'),(SDK/'include/KeplerCPUICB.h','KeplerCPUICB.h')]:shutil.copyfile(source,out/name)
shutil.copytree(SDK/'assets',out/'assets')
inputs={'executable_SHA256':sha(out/'application'),'static_library_SHA256':sha(SDK/'lib/libKeplerMetal.a'),'source_hashes':{n:sha(out/n) for n in ['client.mm','KeplerCPUICB.h']},'assets_SHA256':{x.name:sha(x) for x in (out/'assets').iterdir() if x.is_file()},'core_source_compilations':0}
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(json.dumps({'application':str(out/'application'),'core_source_compilations':0,'static_library_SHA256':inputs['static_library_SHA256']},indent=2))
