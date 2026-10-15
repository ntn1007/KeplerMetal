#!/usr/bin/env python3
"""Compile only the application and its shader, linked to the delivered SDK."""
from pathlib import Path
import argparse,hashlib,json,subprocess
SDK=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-2000:]
air=out/'client.air';lib=out/'client.metallib';run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(SDK/'examples/client.metal'),'-o',str(air)],'air');run(['xcrun','-sdk','macosx','metallib',str(air),'-o',str(lib)],'metallib')
manifest={'schema':1,'library_SHA256':sha(lib),'pipelines':[{'name':'client','vertex':'client_vertex','fragment':'client_fragment','attributes':[],'layouts':[],'target_width':128,'target_height':96,'color_format':80,'direct_geometry':{'start':0,'count':3,'instances':1,'base_instance':0}}]};(out/'client.json').write_text(json.dumps(manifest,indent=2)+'\n');exe=out/'keplermetal_example'
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(SDK/'include'),str(SDK/'examples/client.mm'),'-L',str(SDK/'lib'),'-lKeplerMetal','-Wl,-ObjC','-framework','Foundation','-framework','Metal','-o',str(exe)],'application')
(out/'inputs.json').write_text(json.dumps({'SDK_archive_SHA256':sha(SDK/'lib/libKeplerMetal.a'),'public_header_SHA256':sha(SDK/'include/KeplerCPUICB.h'),'client_source_SHA256':sha(SDK/'examples/client.mm'),'client_shader_source_SHA256':sha(SDK/'examples/client.metal'),'client_shader_SHA256':sha(lib),'client_manifest_SHA256':sha(out/'client.json'),'client_executable_SHA256':sha(exe),'core_source_compilations':0},indent=2)+'\n');print(json.dumps({'client_executable':str(exe),'core_source_compilations':0,'SDK_archive_SHA256':sha(SDK/'lib/libKeplerMetal.a')},indent=2))
