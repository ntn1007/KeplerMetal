#!/usr/bin/env python3
"""Public-client build; generate only input bits, never GPU answers."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
from fp64_reverse_inputs import columns,packed
SDK=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
argv=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(SDK/'include'),str(SDK/'examples/fp64_reverse_client.mm'),'-L',str(SDK/'lib'),'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr[-2000:]
for source in ['examples/fp64_reverse_client.mm','include/KeplerFP64.h']:shutil.copyfile(SDK/source,out/Path(source).name)
shutil.copytree(SDK/'assets',out/'assets')
for trial,(local,count) in enumerate([(32,65),(128,2057),(1024,12289)]):(out/'assets'/f'reverse-input-l{local}-t{trial}.bin').write_bytes(packed(columns('to_f32_rn',local,count,trial)[0]))
(out/'inputs.json').write_text(json.dumps({'executable_SHA256':sha(out/'application'),'static_library_SHA256':sha(SDK/'lib/libKeplerMetal.a'),'source_hashes':{n:sha(out/n) for n in ['fp64_reverse_client.mm','KeplerFP64.h']},'assets_SHA256':{p.name:sha(p) for p in (out/'assets').iterdir() if p.is_file()},'input_generator_SHA256':sha(SDK/'examples/fp64_reverse_inputs.py'),'core_source_compilations':0},indent=2)+'\n');print(json.dumps({'application':str(out/'application'),'core_source_compilations':0}))
