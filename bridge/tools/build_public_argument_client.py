#!/usr/bin/env python3
"""Build the same reception client with public or legacy root bindings."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--public',action='store_true');p.add_argument('--refusals',action='store_true');p.add_argument('--function',action='store_true');a=p.parse_args();a.public=a.public or a.function;out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/command-ir-dataflow-client-build-20261015-04';base=json.loads((old/'inputs.json').read_text());library=a.library.resolve();lm=json.loads((library/'manifest.json').read_text());assert sha(library/'libKeplerMetal.a')==lm['static_library_SHA256']
for n,h in base['assets_SHA256'].items():assert sha(old/'assets'/n)==h
for n,h in base['runtime_SHA256'].items():assert sha(old/'runtime'/n)==h
shutil.copytree(old/'assets',out/'assets');shutil.copytree(old/'runtime',out/'runtime')
if a.function:
 p=ROOT/'results/command-ir-dataflow-compiler-build-20261015/producer.metallib';assert sha(p)=='a9367d4492cd100adfcde990efe0b043e4b070536a3615be5b9b2f63bfb473db';shutil.copyfile(p,out/'assets/producer.metallib')
for name in ['KeplerProgramImport.h','KeplerProgramImport.mm']:shutil.copyfile(ROOT/'src'/name,out/name)
shutil.copyfile(library/'src/KeplerCPUICB.h',out/'KeplerCPUICB.h');shutil.copyfile(ROOT/'tools/command_ir_dataflow_client.mm',out/'command_ir_dataflow_client.mm')
shutil.copyfile(ROOT/'tools/PublicArgumentRefusals.inc',out/'PublicArgumentRefusals.inc')
assert(out/'KeplerProgramImport.h').read_text().count('NS_RETURNS_RETAINED')==6
commands=[]
for label,cmd in [('import',['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out,'-c',out/'KeplerProgramImport.mm','-o',out/'KeplerProgramImport.o']),('host',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_DATAFLOW_NATIVE=0','-DKP_PUBLIC_ARGUMENT_ENCODER='+str(int(a.public)),'-DKP_ARGUMENT_REFUSALS='+str(int(a.refusals)),'-DKP_FUNCTION_ARGUMENT_ENCODER='+str(int(a.function)),'-I',out,out/'command_ir_dataflow_client.mm',out/'KeplerProgramImport.o',library/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])]:
 cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2500:]
inp={'source_hashes':{n:sha(out/n)for n in ['KeplerCPUICB.h','KeplerProgramImport.h','KeplerProgramImport.mm','command_ir_dataflow_client.mm','PublicArgumentRefusals.inc']},'assets_SHA256':{p.name:sha(p)for p in(out/'assets').iterdir()},'runtime_SHA256':{n:sha(out/'runtime'/n)for n in base['runtime_SHA256']},'static_library_SHA256':sha(library/'libKeplerMetal.a'),'library_build_manifest_SHA256':sha(library/'manifest.json'),'source_parent_inputs_SHA256':sha(old/'inputs.json'),'source_generator_SHA256':sha(__file__),'public_argument_encoder':a.public,'argument_refusals':a.refusals,'function_argument_encoder':a.function,'executable_SHA256':sha(out/'application'),'GPU_execution':False}
(out/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'public':a.public,'library':inp['static_library_SHA256']}))
