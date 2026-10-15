#!/usr/bin/env python3
"""Build ARC lifetime probes using already qualified shader bytes, not a new Mesa."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'assets').mkdir();(out/'runtime').mkdir();commands=[]
v=ROOT/'results/vertex-io-qualified';t=ROOT/'results/tessellation-capture-final';r=ROOT/'results/resource-final';vm=json.loads((v/'manifest.json').read_text());tm=json.loads((t/'manifest.json').read_text());rm=json.loads((r/'manifest.json').read_text())
for source,name,expected in [(v/'vertex_io_carrier.metallib','vertex.metallib',vm['carrier_metallib_sha256']),(t/'carrier.metallib','tess.metallib',tm['carrier_metallib_sha256']),(r/'resource_carrier.metallib','resource.metallib',rm['carrier_metallib_sha256'])]:assert sha(source)==expected;shutil.copyfile(source,out/'assets'/name)
for name in ['vertex','flat']:
 row=next(s for s in vm['shaders']if s['kind']==name);source=ROOT/row['path'];assert sha(source)==row['sha256'];shutil.copyfile(source,out/'assets'/(name+'.sass'));(out/'assets'/(name+'.json')).write_text(json.dumps(row['info'],indent=2)+'\n')
assert sha(t/'capture.sass')==tm['code_sha256'];shutil.copyfile(t/'capture.sass',out/'assets/tess.sass');(out/'assets/tess.json').write_text(json.dumps(tm['shader_info'],indent=2)+'\n')
for f in [ROOT/'tools/graphics_factory_lifetime_client.mm',ROOT/'src/KeplerProgramImport.h',ROOT/'src/KeplerProgramImport.mm']:shutil.copyfile(f,out/f.name)
assert(out/'KeplerProgramImport.h').read_text().count('NS_RETURNS_RETAINED')==6
runtime=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK/runtime'
for name in ['run_sdk_host.py','lab_gpu_reservation.py']:shutil.copyfile(runtime/name,out/'runtime'/name)
for label,cmd in [('import-MRC',['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out,'-c',out/'KeplerProgramImport.mm','-o',out/'KeplerProgramImport.o']),('host-ARC',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out,out/'graphics_factory_lifetime_client.mm',out/'KeplerProgramImport.o','-framework','Metal','-framework','Foundation','-o',out/'application'])]:
 cmd=[str(x)for x in cmd];p=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(p.stdout);(out/(label+'.stderr')).write_text(p.stderr);commands.append({'label':label,'argv':cmd,'exit_code':p.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not p.returncode,p.stderr[-4000:]
inputs={'source_hashes':{n:sha(out/n)for n in ['graphics_factory_lifetime_client.mm','KeplerProgramImport.h','KeplerProgramImport.mm']},'assets_SHA256':{p.name:sha(p)for p in(out/'assets').iterdir()},'runtime_SHA256':{p.name:sha(p)for p in(out/'runtime').iterdir()},'executable_SHA256':sha(out/'application'),'shader_provenance_manifests':{str(p.relative_to(ROOT)):sha(p)for p in [v/'manifest.json',t/'manifest.json',r/'manifest.json']},'import_object_SHA256':sha(out/'KeplerProgramImport.o'),'source_generator_SHA256':sha(__file__),'GPU_execution':False,'Mesa_rebuilt':False}
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'GPU_execution':False,'Mesa_rebuilt':False}))
