#!/usr/bin/env python3
"""Rebuild the changed ICB runtime and reuse hash-verified qualified modules."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'src').mkdir()
sdk=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-02/KeplerMetalSDK';base=json.loads((sdk/'BUILD_MANIFEST.json').read_text());objects=[]
for n in ['KeplerCPUICB.h','KeplerCPUICB.mm','KeplerCommandIR.h','KeplerCommandIRScope.inc','KeplerCommandIRv2Scope.inc','KeplerCommandIRPlan.inc','KeplerCommandIRArgumentEncoder.inc','KeplerCommandIRFunction.inc','KeplerCommandIRFunctionScope.inc','KeplerCommandIRProducer.inc','KeplerCommandIRProducerScope.inc','KeplerCommandIRProducerFactory.mm','KeplerProgramImport.h','KeplerNativeCommands.h','KeplerNativeCommands.mm','KeplerResourceABI.h']:shutil.copyfile(ROOT/'src'/n,out/'src'/n)
for name in ['KeplerNativeRenderDraws','KeplerNativeCAS','KeplerFP64']:
 obj=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-02'/(name+'.o');assert sha(obj)==base['object_SHA256'][obj.name];objects.append(obj)
commands=[]
for label,args in [('compile-producer',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(out/'src'),'-c',str(out/'src/KeplerCommandIRProducerFactory.mm'),'-o',str(out/'KeplerCommandIRProducerFactory.o')]),('compile-native',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(out/'src'),'-c',str(out/'src/KeplerNativeCommands.mm'),'-o',str(out/'KeplerNativeCommands.o')]),('compile',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(out/'src'),'-c',str(out/'src/KeplerCPUICB.mm'),'-o',str(out/'KeplerCPUICB.o')]),('archive',['ar','rcs',str(out/'libKeplerMetal.a'),str(out/'KeplerCPUICB.o'),str(out/'KeplerNativeCommands.o'),str(out/'KeplerCommandIRProducerFactory.o'),*[str(x)for x in objects]])]:
 r=subprocess.run(args,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':args,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2500:]
(out/'manifest.json').write_text(json.dumps({'status':'PASS','source_SHA256':{str(p.relative_to(out)):sha(p)for p in(out/'src').iterdir()},'reused_object_SHA256':{str(p):sha(p)for p in objects},'static_library_SHA256':sha(out/'libKeplerMetal.a'),'GPU_execution':False},indent=2)+'\n');print(json.dumps({'status':'PASS','library_SHA256':sha(out/'libKeplerMetal.a')}))
