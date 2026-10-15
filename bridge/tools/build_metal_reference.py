#!/usr/bin/env python3
"""Portable Metal behavior client build. Root is the script's parent tree.

An exported bundle uses the same tools/src layout. Native builds do not link
KeplerMetal. Shader compilation occurs on the target host unless a qualified
metallib is explicitly supplied. No GPU context is created by this builder.
"""
from pathlib import Path
import argparse,hashlib,json,platform,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--adapter-sdk',type=Path);p.add_argument('--metallib',type=Path);a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);(out/'assets').mkdir();(out/'runtime').mkdir();commands=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,r.stderr[-3000:]
source=out/'metal_reference_client.mm';shutil.copyfile(ROOT/'tools/metal_reference_client.mm',source);shutil.copyfile(ROOT/'src/KeplerCPUICB.h',out/'KeplerCPUICB.h');shutil.copyfile(ROOT/'src/cpu_icb_literal_lut.metal',out/'cpu_icb_literal_lut.metal')
shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py');shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
for n in ['cpu_icb_literal_lut_values.json','cpu_icb_literal_lut_manifest.json']:shutil.copyfile(ROOT/'src'/n,out/'assets'/n)
lib=out/'assets/literal_lut.metallib'
if a.metallib:shutil.copyfile(a.metallib.resolve(),lib)
else:
 air=out/'literal_lut.air';run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.3','-c',str(out/'cpu_icb_literal_lut.metal'),'-o',str(air)],'metal-compile');run(['xcrun','-sdk','macosx','metallib',str(air),'-o',str(lib)],'metallib')
argv=['clang++','-arch',platform.machine(),'-O2','-std=c++17','-fobjc-arc','-I',str(out),str(source),'-framework','Metal','-framework','Foundation','-o',str(out/'application')];library_sha=None
if a.adapter_sdk:
 sdk=a.adapter_sdk.resolve();assert platform.machine()=='x86_64';build=json.loads((sdk/'BUILD_MANIFEST.json').read_text());library_sha=sha(sdk/'lib/libKeplerMetal.a');assert library_sha==build['static_library_SHA256']
 assert sha(out/'KeplerCPUICB.h')==sha(sdk/'include/KeplerCPUICB.h') and sha(lib)==sha(sdk/'assets/literal_lut.metallib')
 argv[1:1]=['-DKP_REFERENCE_ADAPTER=1'];argv+=['-L',str(sdk/'lib'),'-lKeplerMetal','-Wl,-ObjC']
run(argv,'host-compile')
sources={n:sha(out/n) for n in ['metal_reference_client.mm','KeplerCPUICB.h','cpu_icb_literal_lut.metal']}
data={'executable_SHA256':sha(out/'application'),'source_hashes':sources,'assets_SHA256':{x.name:sha(x) for x in (out/'assets').iterdir()},'runtime_SHA256':{x.name:sha(x) for x in (out/'runtime').iterdir()},'architecture':platform.machine(),'clang':subprocess.check_output(['clang','--version'],text=True),'SDK':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip(),'static_library_SHA256':library_sha,'core_source_compilations':0,'adapter_linked':bool(a.adapter_sdk),'GPU_execution':False}
(out/'inputs.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({'build':'PASS','architecture':data['architecture'],'adapter_linked':data['adapter_linked'],'core_source_compilations':0}))
