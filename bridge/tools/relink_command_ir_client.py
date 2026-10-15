#!/usr/bin/env python3
"""Relink an exact source/assets snapshot against a newer runtime, in a fresh dir."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--client',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--materializer',type=Path);p.add_argument('--producer-leases',action='store_true');p.add_argument('--return-header',type=Path);a=p.parse_args();client=a.client.resolve();library=a.library.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');inp=json.loads((client/'inputs.json').read_text());bm=json.loads((library/'manifest.json').read_text());assert sha(library/'libKeplerMetal.a')==bm['static_library_SHA256']
for n,h in inp['source_hashes'].items():assert sha(client/n)==h
for n,h in inp['assets_SHA256'].items():assert sha(client/'assets'/n)==h
for n,h in inp['runtime_SHA256'].items():assert sha(client/'runtime'/n)==h
shutil.copytree(client,out);sources=[n for n in ['command_ir_grid3d_client.mm','command_ir_dataflow_client.mm','gpu_command_bindings_client.mm']if(out/n).exists()];assert len(sources)==1;source=sources[0];commands=[]
if a.return_header:
 candidate=a.return_header.read_text();header=out/'KeplerProgramImport.h';original=header.read_text();assert candidate.count('NS_RETURNS_RETAINED')==6 and candidate.replace(' NS_RETURNS_RETAINED','')==original;before=sha(header);shutil.copyfile(a.return_header,header);inp['source_hashes'][header.name]=sha(header);inp['return_header_update']={'before_SHA256':before,'after_SHA256':sha(header),'MRC_implementation_and_ARC_caller_recompiled':True}
if a.producer_leases:
 p=out/source;s=p.read_text();patterns={'command_ir_grid3d_client.mm':('push,root,writer,plan','push,root,writer,plan.commandIRProducerResources'),'command_ir_dataflow_client.mm':('root,p,writer,plan','root,p,writer,plan.commandIRProducerResources'),'gpu_command_bindings_client.mm':('root,pushBuffer,IRproducer,plan','root,pushBuffer,IRproducer,plan.commandIRProducerResources')};old,new=patterns[source];old='NSArray*keep=@['+old+'];';new='NSArray*keep=@['+new+'];';assert s.count(old)==1;before=sha(p);p.write_text(s.replace(old,new,1));inp['source_hashes'][source]=sha(p);inp['producer_lease_update']={'source_SHA256_before':before,'source_SHA256_after':sha(p),'generator_SHA256':sha(__file__),'scope':'Retain immutable commandIRProducerResources without capturing the plan/CB cycle'}
if a.materializer:
 materializer=a.materializer.resolve();shader=materializer/'command_ir_materializer.metallib';assert sha(shader)==json.loads((materializer/'receipt.json').read_text())['shader_SHA256']
 targets=[n for n in ['materializer.metallib','command_ir_materializer.metallib']if(out/'assets'/n).exists()];assert len(targets)==1;name=targets[0];previous=sha(out/'assets'/name);shutil.copyfile(shader,out/'assets'/name);inp['assets_SHA256'][name]=sha(shader);inp['materializer_override']={'previous_SHA256':previous,'current_SHA256':sha(shader),'receipt_SHA256':sha(materializer/'receipt.json')}
for label,cmd in [('import-MRC',['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out,'-c',out/'KeplerProgramImport.mm','-o',out/'KeplerProgramImport.o']),('host',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_GRID_NATIVE=0','-DKP_DATAFLOW_NATIVE=0','-I',out,out/source,out/'KeplerProgramImport.o','-L',library,'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])]:
 cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/('relink-'+label+'.stderr')).write_text(r.stderr);commands.append({'argv':cmd,'exit_code':r.returncode});(out/'relink-commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-3000:]
inp.update(executable_SHA256=sha(out/'application'),static_library_SHA256=sha(library/'libKeplerMetal.a'),relink_source_inputs_SHA256=sha(client/'inputs.json'),relink_library_manifest_SHA256=sha(library/'manifest.json'))
for key in ['library_build_manifest_SHA256','library_manifest_SHA256']:
 if key in inp:inp[key]=sha(library/'manifest.json')
(out/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'library_SHA256':inp['static_library_SHA256'],'source_bytes_unchanged':not(a.producer_leases or a.return_header),'asset_bytes_unchanged':not bool(a.materializer)}))
