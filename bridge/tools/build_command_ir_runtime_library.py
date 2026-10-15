#!/usr/bin/env python3
"""Build an immutable runtime from all current module sources; no object reuse."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'src').mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
names=['KeplerCPUICB','KeplerNativeCommands','KeplerNativeRenderDraws','KeplerNativeCAS','KeplerFP64','KeplerCommandIRProducerFactory']
for source in (ROOT/'src').iterdir():
 if source.suffix in ['.h','.inc']or(source.suffix=='.mm'and source.stem in names):shutil.copyfile(source,out/'src'/source.name)
pins=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-02/KeplerMetalSDK/src/KeplerFP64Programs.inc'
shutil.copyfile(pins,out/'src/KeplerFP64Programs.inc')
commands=[];objects=[]
def run(label,argv):
 argv=[str(x)for x in argv];r=subprocess.run(argv,capture_output=True,text=True,timeout=55);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-3000:];print(label,'PASS',flush=True)
for name in names:
 obj=out/(name+'.o');run('compile-'+name,['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc'if name=='KeplerNativeCAS'else'-fobjc-arc','-I',out/'src','-c',out/'src'/(name+'.mm'),'-o',obj]);objects.append(obj)
run('archive',['ar','rcs',out/'libKeplerMetal.a',*objects])
(out/'manifest.json').write_text(json.dumps({'status':'PASS','source_SHA256':{str(p.relative_to(out)):sha(p)for p in(out/'src').iterdir()},'object_SHA256':{p.name:sha(p)for p in objects},'reused_object_SHA256':{},'static_library_SHA256':sha(out/'libKeplerMetal.a'),'GPU_execution':False,'all_runtime_modules_rebuilt':True},indent=2)+'\n')
print(json.dumps({'status':'PASS','library_SHA256':sha(out/'libKeplerMetal.a')}))
