#!/usr/bin/env python3
"""Build a conversion client using only the public header and static SDK."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess
SDK=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
argv=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(SDK/'include'),str(SDK/'examples/fp64_conversion_client.mm'),'-L',str(SDK/'lib'),'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr[-2000:]
for src in ['examples/fp64_conversion_client.mm','include/KeplerFP64.h']:shutil.copyfile(SDK/src,out/Path(src).name)
shutil.copytree(SDK/'assets',out/'assets')
(out/'inputs.json').write_text(json.dumps({'executable_SHA256':sha(out/'application'),'static_library_SHA256':sha(SDK/'lib/libKeplerMetal.a'),'source_hashes':{n:sha(out/n) for n in ['fp64_conversion_client.mm','KeplerFP64.h']},'assets_SHA256':{p.name:sha(p) for p in (out/'assets').iterdir() if p.is_file()},'core_source_compilations':0},indent=2)+'\n')
print(json.dumps({'application':str(out/'application'),'core_source_compilations':0}))
