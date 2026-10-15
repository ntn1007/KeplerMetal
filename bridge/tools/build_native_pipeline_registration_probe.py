#!/usr/bin/env python3
"""Metadata/ownership test with registered PSO surviving its restored scope."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--library',type=Path,required=True);a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/function-argument-registration-build-20261015-02';base=json.loads((old/'inputs.json').read_text());lib=a.library.resolve();lm=json.loads((lib/'manifest.json').read_text());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert sha(lib/'libKeplerMetal.a')==lm['static_library_SHA256']
for key,folder in [('source_hashes',old),('assets_SHA256',old/'assets'),('runtime_SHA256',old/'runtime')]:
 for n,h in base[key].items():assert sha(folder/n)==h
shutil.copytree(old/'assets',out/'assets');shutil.copytree(old/'runtime',out/'runtime')
for n in base['source_hashes']:shutil.copyfile(old/n,out/n)
shutil.copyfile(lib/'src/KeplerCPUICB.h',out/'KeplerCPUICB.h')
compiler=ROOT/'results/native-resource-command-compiler-build-20261015-02'
for src,name in [(compiler/'carrier.metallib','native-carrier.metallib'),(compiler/'basic/program.sass','native-basic.sass')]:shutil.copyfile(src,out/'assets'/name)
s=(out/'function_argument_registration_probe.mm').read_text();anchor='id<MTLFunction>surviving=nil;';assert s.count(anchor)==1;s=s.replace(anchor,anchor+'id<MTLComputePipelineState>survivingPipeline=nil;',1)
lines=s.splitlines();indices=[i for i,x in enumerate(lines)if'[name setString:@"changed_by_caller"]'in x];assert len(indices)==1
lines.insert(indices[0]+1,'''   NSData*carrier=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"native-carrier.metallib"]],*program=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"native-basic.sass"]];
   if(![s registerCommandIRProducerForFunction:surviving carrierData:carrier programData:program error:&error])return 12;
   survivingPipeline=[d newComputePipelineStateWithFunction:surviving error:&error];if(!survivingPipeline)return 12;
   [checks addObject:@{@"case":@"registered_pipeline_after_caller_mutation",@"PASS":@YES}];''')
indices=[i for i,x in enumerate(lines)if'row[@"scope_released"]=@YES'in x];assert len(indices)==1
lines.insert(indices[0],'''  NSError*restoredError=nil;if(!survivingPipeline||[d newComputePipelineStateWithFunction:surviving error:&restoredError]||![restoredError.description containsString:@"air.compute_pipeline_state"])return 13;
  row[@"native_pipeline_survived_scope"]=@YES;row[@"native_factory_restored"]=@YES;''')
(out/'function_argument_registration_probe.mm').write_text('\n'.join(lines)+'\n')
cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out,out/'function_argument_registration_probe.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'];cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/'host.stdout').write_text(r.stdout);(out/'host.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n');assert not r.returncode,r.stderr[-2000:]
base.update(source_hashes={n:sha(out/n)for n in base['source_hashes']},assets_SHA256={p.name:sha(p)for p in(out/'assets').iterdir()},static_library_SHA256=sha(lib/'libKeplerMetal.a'),library_build_manifest_SHA256=sha(lib/'manifest.json'),source_generator_SHA256=sha(__file__),executable_SHA256=sha(out/'application'),source_parent_inputs_SHA256=sha(old/'inputs.json'),registered_pipeline_lifetime=True)
(out/'inputs.json').write_text(json.dumps(base,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'GPU_execution':False}))
