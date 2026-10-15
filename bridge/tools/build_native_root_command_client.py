#!/usr/bin/env python3
"""Freeze the qualified reception client with native resource ABI producers."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--compiler',type=Path,required=True);a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/function-argument-client-final-build-20261015';m=json.loads((old/'inputs.json').read_text());compiler=a.compiler.resolve();cm=json.loads((compiler/'manifest.json').read_text())
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
for key,folder in [('source_hashes',old),('assets_SHA256',old/'assets'),('runtime_SHA256',old/'runtime')]:
 for n,h in m[key].items():assert sha(folder/n)==h
assert sha(compiler/'carrier.metallib')==cm['carrier_metallib_SHA256']
shutil.copytree(old/'assets',out/'assets');shutil.copytree(old/'runtime',out/'runtime')
for n in m['source_hashes']:shutil.copyfile(old/n,out/n)
for row in cm['records']:
 name=row['semantic'];assert sha(compiler/name/'program.sass')==row['code_SHA256'];shutil.copyfile(compiler/name/'program.sass',out/'assets'/(name+'.sass'));shutil.copyfile(compiler/name/'info.json',out/'assets'/(name+'.json'))
shutil.copyfile(compiler/'carrier.metallib',out/'assets/carrier.metallib')
s=(out/'command_ir_dataflow_client.mm').read_text();anchor='@"command_ir_carrier"';assert s.count(anchor)==1;s=s.replace(anchor,'@"command_ir_native_root_carrier"',1)
lines=s.splitlines();matches=[i for i,x in enumerate(lines)if 'Push push={root.gpuAddress' in x];assert len(matches)==1
lines[matches[0]]='''    [e setBuffer:root offset:0 atIndex:0];[e useResource:root usage:MTLResourceUsageRead];for(id<MTLBuffer>r in plan.commandIRProducerResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];NSArray*keep=@[root,writer,plan.commandIRProducerResources];[pbuf addCompletedHandler:^(id<MTLCommandBuffer>c){(void)keep.count;}];'''
s='\n'.join(lines)+'\n';anchor='@"function_argument_encoder":@(KP_FUNCTION_ARGUMENT_ENCODER)';assert s.count(anchor)==1;s=s.replace(anchor,anchor+',@"native_root_binding":@YES,@"host_push_buffer_required":@NO',1)
(out/'command_ir_dataflow_client.mm').write_text(s);commands=[]
lib=ROOT/'results/function-argument-runtime-library-build-20261015-03';assert sha(lib/'libKeplerMetal.a')==m['static_library_SHA256']
for label,cmd in [('import',['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out,'-c',out/'KeplerProgramImport.mm','-o',out/'KeplerProgramImport.o']),('host',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_DATAFLOW_NATIVE=0','-DKP_PUBLIC_ARGUMENT_ENCODER=1','-DKP_FUNCTION_ARGUMENT_ENCODER=1','-DKP_ARGUMENT_REFUSALS=0','-I',out,out/'command_ir_dataflow_client.mm',out/'KeplerProgramImport.o',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])]:
 cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2000:]
m.update(source_hashes={n:sha(out/n)for n in m['source_hashes']},assets_SHA256={n:sha(out/'assets'/n)for n in m['assets_SHA256']},executable_SHA256=sha(out/'application'),source_parent_inputs_SHA256=sha(old/'inputs.json'),native_compiler_manifest_SHA256=sha(compiler/'manifest.json'),source_generator_SHA256=sha(__file__),native_root_binding=True,host_push_buffer_required=False,GPU_execution=False)
(out/'inputs.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'native_root_binding':True,'GPU_execution':False}))
